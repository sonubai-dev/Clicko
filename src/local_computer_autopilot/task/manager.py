"""Task Manager coordinating task lifecycle and execution step tracking."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from local_computer_autopilot.task.models import (
    StepRecord,
    StepStatus,
    TaskRecord,
    TaskStatus,
)
from local_computer_autopilot.task.storage import TaskStorage

logger = logging.getLogger("local_computer_autopilot.task.manager")


class TaskManager:
    """Coordinates task creation, status updates, and step auditing."""

    def __init__(self, storage: TaskStorage | None = None, db_path: str | Path | None = None) -> None:
        if storage is not None:
            self._storage = storage
        else:
            path = db_path or Path("data") / "clicko_tasks.db"
            self._storage = TaskStorage(path)
        self._active_task_id: str | None = None

    @property
    def active_task_id(self) -> str | None:
        return self._active_task_id

    @property
    def storage(self) -> TaskStorage:
        return self._storage

    def create_task(self, description: str, task_id: str | None = None) -> TaskRecord:
        """Create and start a new task."""
        tid = task_id or f"task_{uuid.uuid4().hex[:8]}"
        task = self._storage.create_task(tid, description)
        self._active_task_id = tid
        logger.info("Task created: %s - %s", tid, description)
        return task

    def complete_task(self, task_id: str) -> None:
        """Mark task as successfully completed."""
        self._storage.update_task_status(task_id, TaskStatus.COMPLETED)
        if self._active_task_id == task_id:
            self._active_task_id = None
        logger.info("Task completed: %s", task_id)

    def fail_task(self, task_id: str, error_message: str) -> None:
        """Mark task as failed."""
        self._storage.update_task_status(task_id, TaskStatus.FAILED, error_message)
        if self._active_task_id == task_id:
            self._active_task_id = None
        logger.warning("Task failed: %s (%s)", task_id, error_message)

    def cancel_task(self, task_id: str) -> None:
        """Mark task as cancelled."""
        self._storage.update_task_status(task_id, TaskStatus.CANCELLED)
        if self._active_task_id == task_id:
            self._active_task_id = None
        logger.info("Task cancelled: %s", task_id)

    def record_step(
        self,
        task_id: str,
        action_name: str,
        parameters: dict[str, Any] | None = None,
        status: StepStatus = StepStatus.SUCCESS,
        result_summary: str | None = None,
        error_message: str | None = None,
        visual_verified: bool = False,
    ) -> StepRecord:
        """Record an action step taken within a task."""
        params = parameters or {}
        step = self._storage.record_step(
            task_id=task_id,
            action_name=action_name,
            parameters=params,
            status=status,
            result_summary=result_summary,
            error_message=error_message,
            visual_verified=visual_verified,
        )
        logger.debug(
            "Task %s recorded step %d: %s (%s)",
            task_id,
            step.step_number,
            action_name,
            status.value,
        )
        return step

    def get_task_status(self, task_id: str) -> dict[str, Any]:
        """Return structured task summary including step details."""
        task = self._storage.get_task(task_id)
        if not task:
            return {"found": False, "task_id": task_id}

        steps = self._storage.list_steps(task_id)
        return {
            "found": True,
            "task": task.model_dump(),
            "steps": [s.model_dump() for s in steps],
        }

    def list_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """List recently executed tasks."""
        tasks = self._storage.list_tasks(limit=limit)
        return [t.model_dump() for t in tasks]
