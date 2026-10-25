"""Unit tests for Phase 5 Workflow Scheduler and ScheduleStorage."""

from __future__ import annotations

import time
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
import pytest

from local_computer_autopilot.agent.models import ExecutionResult
from local_computer_autopilot.scheduler.models import ScheduleDefinition
from local_computer_autopilot.scheduler.service import WorkflowScheduler
from local_computer_autopilot.scheduler.storage import ScheduleStorage


@pytest.fixture
def memory_storage():
    return ScheduleStorage(db_path=":memory:")


class TestScheduleStorage:
    def test_create_and_get_schedule(self, memory_storage):
        sched = memory_storage.create_schedule(
            name="Daily Backup",
            interval_seconds=3600,
            target="backup all local files",
            is_macro=False,
        )
        assert sched.id.startswith("sched_")
        assert sched.name == "Daily Backup"
        assert sched.interval_seconds == 3600
        assert sched.enabled is True
        assert sched.run_count == 0

        # Retrieve by ID
        fetched = memory_storage.get_schedule(sched.id)
        assert fetched is not None
        assert fetched.name == "Daily Backup"

        # Retrieve by Name
        fetched_name = memory_storage.get_schedule("Daily Backup")
        assert fetched_name is not None
        assert fetched_name.id == sched.id

    def test_list_and_delete_schedule(self, memory_storage):
        s1 = memory_storage.create_schedule("Task A", 60, "goal a")
        s2 = memory_storage.create_schedule("Task B", 120, "goal b")

        all_s = memory_storage.list_schedules()
        assert len(all_s) == 2

        deleted = memory_storage.delete_schedule(s1.id)
        assert deleted is True

        remaining = memory_storage.list_schedules()
        assert len(remaining) == 1
        assert remaining[0].name == "Task B"

    def test_toggle_schedule(self, memory_storage):
        s = memory_storage.create_schedule("Toggle Target", 60, "goal")
        assert s.enabled is True

        toggled = memory_storage.toggle_schedule(s.id, False)
        assert toggled is True

        fetched = memory_storage.get_schedule(s.id)
        assert fetched.enabled is False

    def test_record_run(self, memory_storage):
        s = memory_storage.create_schedule("Run Tracker", 300, "goal")
        memory_storage.record_run(s.id)

        updated = memory_storage.get_schedule(s.id)
        assert updated.run_count == 1
        assert updated.last_run is not None


class TestWorkflowSchedulerService:
    def test_run_due_schedules_agent_goal(self, memory_storage):
        # Create a schedule that is already due in the past
        sched = memory_storage.create_schedule("Past Due Goal", 60, "do immediate work")
        # Artificially set next_run to 10 seconds ago
        past_iso = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        with memory_storage._conn:
            memory_storage._conn.execute(
                "UPDATE schedules SET next_run = ? WHERE id = ?", (past_iso, sched.id)
            )

        mock_agent = MagicMock()
        mock_plan_res = ExecutionResult(
            task_id="test_task",
            goal="do immediate work",
            success=True,
            status="completed",
            steps_total=1,
            steps_completed=1,
            duration_seconds=0.5,
        )
        mock_agent.run_plan.return_value = mock_plan_res

        mock_planner = MagicMock()
        mock_planner.plan.return_value = MagicMock(steps=[])

        scheduler = WorkflowScheduler(
            storage=memory_storage,
            agent=mock_agent,
            planner=mock_planner,
        )

        results = scheduler.run_due_schedules()
        assert len(results) == 1
        assert results[0].success is True
        assert "Goal 'do immediate work' completed" in results[0].message

        # Verify run was recorded
        updated = memory_storage.get_schedule(sched.id)
        assert updated.run_count == 1

    def test_run_due_schedules_macro(self, memory_storage):
        sched = memory_storage.create_schedule("Past Due Macro", 60, "MyMacro", is_macro=True)
        past_iso = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        with memory_storage._conn:
            memory_storage._conn.execute(
                "UPDATE schedules SET next_run = ? WHERE id = ?", (past_iso, sched.id)
            )

        mock_agent = MagicMock()
        mock_macro_runner = MagicMock()
        mock_macro_res = MagicMock(success=True)
        mock_macro_runner.execute_macro.return_value = mock_macro_res

        scheduler = WorkflowScheduler(
            storage=memory_storage,
            agent=mock_agent,
            macro_runner=mock_macro_runner,
        )

        results = scheduler.run_due_schedules()
        assert len(results) == 1
        assert results[0].success is True
        mock_macro_runner.execute_macro.assert_called_once_with("MyMacro")

    def test_start_and_stop_scheduler(self, memory_storage):
        mock_agent = MagicMock()
        scheduler = WorkflowScheduler(storage=memory_storage, agent=mock_agent)

        scheduler.start(poll_interval=0.1)
        assert scheduler.is_running is True

        scheduler.stop()
        assert scheduler.is_running is False
