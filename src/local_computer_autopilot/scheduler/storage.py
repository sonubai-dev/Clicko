"""SQLite storage for automated recurring schedules."""

from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
import uuid

from local_computer_autopilot.scheduler.models import ScheduleDefinition

logger = logging.getLogger("local_computer_autopilot.scheduler")


class ScheduleStorage:
    """Thread-safe SQLite storage for workflow schedules."""

    def __init__(self, db_path: str = "data/schedules.sqlite") -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            with self._conn:
                self._conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schedules (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL UNIQUE,
                        interval_seconds INTEGER NOT NULL,
                        target TEXT NOT NULL,
                        is_macro INTEGER NOT NULL DEFAULT 0,
                        enabled INTEGER NOT NULL DEFAULT 1,
                        last_run TEXT,
                        next_run TEXT NOT NULL,
                        run_count INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )

    def create_schedule(
        self,
        name: str,
        interval_seconds: int,
        target: str,
        is_macro: bool = False,
    ) -> ScheduleDefinition:
        """Create and persist a new workflow schedule."""
        clean_name = name.strip()
        existing = self.get_schedule(clean_name)
        sched_id = existing.id if existing else f"sched_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)
        next_run = (now + timedelta(seconds=interval_seconds)).isoformat()

        with self._lock:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO schedules (id, name, interval_seconds, target, is_macro, enabled, last_run, next_run, run_count)
                    VALUES (?, ?, ?, ?, ?, 1, NULL, ?, 0)
                    ON CONFLICT(name) DO UPDATE SET
                        interval_seconds = excluded.interval_seconds,
                        target = excluded.target,
                        is_macro = excluded.is_macro,
                        enabled = 1,
                        next_run = excluded.next_run
                    """,
                    (
                        sched_id,
                        clean_name,
                        interval_seconds,
                        target.strip(),
                        1 if is_macro else 0,
                        next_run,
                    ),
                )

        logger.info("Created schedule '%s' (every %ds)", clean_name, interval_seconds)
        return ScheduleDefinition(
            id=sched_id,
            name=clean_name,
            interval_seconds=interval_seconds,
            target=target.strip(),
            is_macro=is_macro,
            enabled=True,
            last_run=None,
            next_run=next_run,
            run_count=0,
        )

    def list_schedules(self) -> list[ScheduleDefinition]:
        """List all registered schedules."""
        with self._lock:
            cursor = self._conn.execute(
                "SELECT id, name, interval_seconds, target, is_macro, enabled, last_run, next_run, run_count FROM schedules ORDER BY next_run ASC"
            )
            rows = cursor.fetchall()

        schedules = []
        for r in rows:
            schedules.append(
                ScheduleDefinition(
                    id=r["id"],
                    name=r["name"],
                    interval_seconds=r["interval_seconds"],
                    target=r["target"],
                    is_macro=bool(r["is_macro"]),
                    enabled=bool(r["enabled"]),
                    last_run=r["last_run"],
                    next_run=r["next_run"],
                    run_count=r["run_count"],
                )
            )
        return schedules

    def get_schedule(self, identifier: str) -> ScheduleDefinition | None:
        """Retrieve a schedule by ID or name."""
        with self._lock:
            cursor = self._conn.execute(
                "SELECT id, name, interval_seconds, target, is_macro, enabled, last_run, next_run, run_count FROM schedules WHERE id = ? OR name = ?",
                (identifier.strip(), identifier.strip()),
            )
            row = cursor.fetchone()

        if not row:
            return None

        return ScheduleDefinition(
            id=row["id"],
            name=row["name"],
            interval_seconds=row["interval_seconds"],
            target=row["target"],
            is_macro=bool(row["is_macro"]),
            enabled=bool(row["enabled"]),
            last_run=row["last_run"],
            next_run=row["next_run"],
            run_count=row["run_count"],
        )

    def delete_schedule(self, identifier: str) -> bool:
        """Delete a schedule by ID or name."""
        with self._lock:
            with self._conn:
                cursor = self._conn.execute(
                    "DELETE FROM schedules WHERE id = ? OR name = ?",
                    (identifier.strip(), identifier.strip()),
                )
                deleted = cursor.rowcount > 0

        if deleted:
            logger.info("Deleted schedule '%s'", identifier)
        return deleted

    def toggle_schedule(self, identifier: str, enabled: bool) -> bool:
        """Enable or disable a schedule."""
        with self._lock:
            with self._conn:
                cursor = self._conn.execute(
                    "UPDATE schedules SET enabled = ? WHERE id = ? OR name = ?",
                    (1 if enabled else 0, identifier.strip(), identifier.strip()),
                )
                updated = cursor.rowcount > 0

        return updated

    def record_run(self, schedule_id: str) -> None:
        """Update last_run, next_run, and run_count upon execution."""
        sched = self.get_schedule(schedule_id)
        if not sched:
            return

        now = datetime.now(timezone.utc)
        next_run = (now + timedelta(seconds=sched.interval_seconds)).isoformat()

        with self._lock:
            with self._conn:
                self._conn.execute(
                    """
                    UPDATE schedules
                    SET last_run = ?, next_run = ?, run_count = run_count + 1
                    WHERE id = ?
                    """,
                    (now.isoformat(), next_run, schedule_id),
                )
