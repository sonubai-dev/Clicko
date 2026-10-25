"""SQLite storage for Macro definitions."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

from local_computer_autopilot.macros.models import MacroDefinition

logger = logging.getLogger("local_computer_autopilot.macros")


class MacroStorage:
    """Thread-safe SQLite storage for automation macros."""

    def __init__(self, db_path: str = "data/macros.sqlite") -> None:
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
                    CREATE TABLE IF NOT EXISTS macros (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL UNIQUE,
                        description TEXT,
                        created_at TEXT NOT NULL,
                        steps_json TEXT NOT NULL,
                        parameters_json TEXT NOT NULL
                    )
                    """
                )

    def create_macro(
        self,
        name: str,
        description: str,
        steps: list[dict[str, Any]],
        parameters: list[str] | None = None,
    ) -> MacroDefinition:
        """Create and persist a new automation macro."""
        macro_id = f"macro_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()
        params = parameters or []

        with self._lock:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO macros (id, name, description, created_at, steps_json, parameters_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        macro_id,
                        name.strip(),
                        description.strip(),
                        created_at,
                        json.dumps(steps),
                        json.dumps(params),
                    ),
                )

        logger.info("Created macro '%s' (%s) with %d steps", name, macro_id, len(steps))
        return MacroDefinition(
            id=macro_id,
            name=name.strip(),
            description=description.strip(),
            created_at=created_at,
            steps=steps,
            parameters=params,
        )

    def list_macros(self) -> list[MacroDefinition]:
        """List all stored macros."""
        with self._lock:
            cursor = self._conn.execute(
                "SELECT id, name, description, created_at, steps_json, parameters_json FROM macros ORDER BY created_at DESC"
            )
            rows = cursor.fetchall()

        macros = []
        for r in rows:
            macros.append(
                MacroDefinition(
                    id=r["id"],
                    name=r["name"],
                    description=r["description"],
                    created_at=r["created_at"],
                    steps=json.loads(r["steps_json"]),
                    parameters=json.loads(r["parameters_json"]),
                )
            )
        return macros

    def get_macro(self, identifier: str) -> MacroDefinition | None:
        """Retrieve a macro by ID or exact name."""
        with self._lock:
            cursor = self._conn.execute(
                "SELECT id, name, description, created_at, steps_json, parameters_json FROM macros WHERE id = ? OR name = ?",
                (identifier.strip(), identifier.strip()),
            )
            row = cursor.fetchone()

        if not row:
            return None

        return MacroDefinition(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            created_at=row["created_at"],
            steps=json.loads(row["steps_json"]),
            parameters=json.loads(row["parameters_json"]),
        )

    def delete_macro(self, identifier: str) -> bool:
        """Delete a macro by ID or name."""
        with self._lock:
            with self._conn:
                cursor = self._conn.execute(
                    "DELETE FROM macros WHERE id = ? OR name = ?",
                    (identifier.strip(), identifier.strip()),
                )
                deleted = cursor.rowcount > 0

        if deleted:
            logger.info("Deleted macro '%s'", identifier)
        return deleted
