"""SQLite persistence layer for task tracking."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path

from local_computer_autopilot.task.models import (
    StepRecord,
    StepStatus,
    TaskRecord,
    TaskStatus,
)

logger = logging.getLogger("local_computer_autopilot.task.storage")


class TaskStorage:
    """Manages SQLite storage for tasks and steps."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        self._lock = threading.Lock()
        self._mem_conn: sqlite3.Connection | None = None
        if self.db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._mem_conn.row_factory = sqlite3.Row
        else:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._mem_conn is not None:
            return self._mem_conn
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    error_message TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS steps (
                    step_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    step_number INTEGER NOT NULL,
                    action_name TEXT NOT NULL,
                    parameters TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_summary TEXT,
                    error_message TEXT,
                    visual_verified INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
                """
            )
            conn.commit()

    def create_task(self, task_id: str, description: str) -> TaskRecord:
        now = time.time()
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO tasks (task_id, description, status, created_at, updated_at, error_message)
                VALUES (?, ?, ?, ?, ?, NULL)
                """,
                (task_id, description, TaskStatus.RUNNING.value, now, now),
            )
            conn.commit()
        return TaskRecord(
            task_id=task_id,
            description=description,
            status=TaskStatus.RUNNING,
            created_at=now,
            updated_at=now,
            error_message=None,
            step_count=0,
        )

    def update_task_status(
        self, task_id: str, status: TaskStatus, error_message: str | None = None
    ) -> None:
        now = time.time()
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = ?, updated_at = ?, error_message = ?
                WHERE task_id = ?
                """,
                (status.value, now, error_message, task_id),
            )
            conn.commit()

    def get_task(self, task_id: str) -> TaskRecord | None:
        with self._lock, self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            if not row:
                return None
            step_count = conn.execute(
                "SELECT COUNT(*) FROM steps WHERE task_id = ?", (task_id,)
            ).fetchone()[0]

            return TaskRecord(
                task_id=row["task_id"],
                description=row["description"],
                status=TaskStatus(row["status"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                error_message=row["error_message"],
                step_count=step_count,
            )

    def record_step(
        self,
        task_id: str,
        action_name: str,
        parameters: dict,
        status: StepStatus,
        result_summary: str | None = None,
        error_message: str | None = None,
        visual_verified: bool = False,
    ) -> StepRecord:
        now = time.time()
        with self._lock, self._get_connection() as conn:
            # Determine next step number
            count = conn.execute(
                "SELECT COUNT(*) FROM steps WHERE task_id = ?", (task_id,)
            ).fetchone()[0]
            step_number = count + 1

            params_json = json.dumps(parameters, default=str)
            cur = conn.execute(
                """
                INSERT INTO steps (
                    task_id, step_number, action_name, parameters, status,
                    result_summary, error_message, visual_verified, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    step_number,
                    action_name,
                    params_json,
                    status.value,
                    result_summary,
                    error_message,
                    1 if visual_verified else 0,
                    now,
                ),
            )
            step_id = cur.lastrowid
            conn.commit()

        return StepRecord(
            step_id=step_id,
            task_id=task_id,
            step_number=step_number,
            action_name=action_name,
            parameters=parameters,
            status=status,
            result_summary=result_summary,
            error_message=error_message,
            visual_verified=visual_verified,
            created_at=now,
        )

    def list_steps(self, task_id: str) -> list[StepRecord]:
        with self._lock, self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM steps WHERE task_id = ? ORDER BY step_number ASC",
                (task_id,),
            ).fetchall()

            results = []
            for r in rows:
                params = json.loads(r["parameters"]) if r["parameters"] else {}
                results.append(
                    StepRecord(
                        step_id=r["step_id"],
                        task_id=r["task_id"],
                        step_number=r["step_number"],
                        action_name=r["action_name"],
                        parameters=params,
                        status=StepStatus(r["status"]),
                        result_summary=r["result_summary"],
                        error_message=r["error_message"],
                        visual_verified=bool(r["visual_verified"]),
                        created_at=r["created_at"],
                    )
                )
            return results

    def get_steps(self, task_id: str) -> list[StepRecord]:
        """Alias for list_steps."""
        return self.list_steps(task_id)

    def list_tasks(self, limit: int = 20) -> list[TaskRecord]:
        with self._lock, self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)
            ).fetchall()
            results = []
            for r in rows:
                step_count = conn.execute(
                    "SELECT COUNT(*) FROM steps WHERE task_id = ?", (r["task_id"],)
                ).fetchone()[0]
                results.append(
                    TaskRecord(
                        task_id=r["task_id"],
                        description=r["description"],
                        status=TaskStatus(r["status"]),
                        created_at=r["created_at"],
                        updated_at=r["updated_at"],
                        error_message=r["error_message"],
                        step_count=step_count,
                    )
                )
            return results
