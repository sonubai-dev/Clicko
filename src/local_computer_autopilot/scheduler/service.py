"""Background scheduler service for executing due automated workflows."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from local_computer_autopilot.agent.planner import WorkflowPlanner
from local_computer_autopilot.scheduler.models import ScheduleDefinition, ScheduleExecutionResult
from local_computer_autopilot.scheduler.storage import ScheduleStorage

if TYPE_CHECKING:
    from local_computer_autopilot.agent.runner import AutonomousAgent
    from local_computer_autopilot.macros.runner import MacroRunner

logger = logging.getLogger("local_computer_autopilot.scheduler")


class WorkflowScheduler:
    """Service that manages and executes automated recurring workflows."""

    def __init__(
        self,
        storage: ScheduleStorage,
        agent: AutonomousAgent,
        planner: WorkflowPlanner | None = None,
        macro_runner: MacroRunner | None = None,
    ) -> None:
        self.storage = storage
        self.agent = agent
        self.planner = planner or WorkflowPlanner()
        self.macro_runner = macro_runner

        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    @property
    def is_running(self) -> bool:
        """Check whether the background scheduler thread is running."""
        return self._running

    def run_due_schedules(self) -> list[ScheduleExecutionResult]:
        """Check and execute any due schedules synchronously."""
        results: list[ScheduleExecutionResult] = []
        now = datetime.now(timezone.utc)

        schedules = self.storage.list_schedules()
        for sched in schedules:
            if not sched.enabled:
                continue

            try:
                # Handle next_run format
                due_dt = datetime.fromisoformat(sched.next_run)
                if due_dt.tzinfo is None:
                    due_dt = due_dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue

            if now >= due_dt:
                logger.info("Executing due schedule: '%s' (%s)", sched.name, sched.id)
                success = False
                msg = ""

                try:
                    if sched.is_macro and self.macro_runner is not None:
                        res = self.macro_runner.execute_macro(sched.target)
                        success = res.success
                        msg = f"Macro '{sched.target}' finished: success={res.success}"
                    else:
                        plan = self.planner.plan(sched.target)
                        res_plan = self.agent.run_plan(plan)
                        success = res_plan.success
                        msg = f"Goal '{sched.target}' completed: success={res_plan.success}"
                except Exception as exc:
                    logger.error("Schedule '%s' execution error: %s", sched.name, exc)
                    success = False
                    msg = f"Failed to execute: {exc}"

                self.storage.record_run(sched.id)
                results.append(
                    ScheduleExecutionResult(
                        schedule_id=sched.id,
                        name=sched.name,
                        success=success,
                        executed_at=now.isoformat(),
                        message=msg,
                    )
                )

        return results

    def start(self, poll_interval: float = 2.0) -> None:
        """Start the background scheduler loop in a daemon thread."""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()

        def _loop() -> None:
            logger.info("Workflow scheduler background worker started")
            while not self._stop_event.is_set():
                try:
                    self.run_due_schedules()
                except Exception as exc:
                    logger.error("Error in scheduler worker loop: %s", exc)
                self._stop_event.wait(timeout=poll_interval)
            logger.info("Workflow scheduler background worker stopped")

        self._thread = threading.Thread(target=_loop, daemon=True, name="ClickoScheduler")
        self._thread.start()

    def stop(self) -> None:
        """Cooperatively stop the background scheduler loop."""
        if not self._running:
            return

        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._running = False
