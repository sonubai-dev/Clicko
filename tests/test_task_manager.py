"""Unit tests for SQLite task tracking and auditing."""

from __future__ import annotations

import pytest

from local_computer_autopilot.task.manager import TaskManager
from local_computer_autopilot.task.models import StepStatus, TaskStatus
from local_computer_autopilot.task.storage import TaskStorage


@pytest.fixture()
def memory_storage() -> TaskStorage:
    return TaskStorage(":memory:")


@pytest.fixture()
def task_manager(memory_storage) -> TaskManager:
    return TaskManager(storage=memory_storage)


class TestTaskStorage:
    def test_create_and_get_task(self, memory_storage):
        task = memory_storage.create_task("test_1", "Search for weather")
        assert task.task_id == "test_1"
        assert task.status == TaskStatus.RUNNING

        retrieved = memory_storage.get_task("test_1")
        assert retrieved is not None
        assert retrieved.description == "Search for weather"
        assert retrieved.status == TaskStatus.RUNNING
        assert retrieved.step_count == 0

    def test_update_task_status(self, memory_storage):
        memory_storage.create_task("test_2", "Sample task")
        memory_storage.update_task_status("test_2", TaskStatus.COMPLETED)
        t = memory_storage.get_task("test_2")
        assert t.status == TaskStatus.COMPLETED

    def test_record_and_list_steps(self, memory_storage):
        memory_storage.create_task("t3", "Audit trail test")
        s1 = memory_storage.record_step(
            task_id="t3",
            action_name="computer_click",
            parameters={"x": 100, "y": 200},
            status=StepStatus.SUCCESS,
            result_summary="Clicked button",
            visual_verified=True,
        )
        assert s1.step_number == 1
        assert s1.visual_verified is True

        s2 = memory_storage.record_step(
            task_id="t3",
            action_name="computer_type_text",
            parameters={"text_len": 5},
            status=StepStatus.SUCCESS,
            result_summary="Typed query",
        )
        assert s2.step_number == 2

        steps = memory_storage.list_steps("t3")
        assert len(steps) == 2
        assert steps[0].action_name == "computer_click"
        assert steps[1].action_name == "computer_type_text"

        # Check step_count reflected on task
        t3 = memory_storage.get_task("t3")
        assert t3.step_count == 2


class TestTaskManager:
    def test_lifecycle(self, task_manager):
        task = task_manager.create_task("Automate form submission")
        tid = task.task_id
        assert task_manager.active_task_id == tid

        step = task_manager.record_step(
            task_id=tid,
            action_name="browser_open",
            parameters={"url": "https://example.com"},
            status=StepStatus.SUCCESS,
            result_summary="Opened URL",
        )
        assert step.step_number == 1

        status_info = task_manager.get_task_status(tid)
        assert status_info["found"] is True
        assert status_info["task"]["status"] == "running"
        assert len(status_info["steps"]) == 1

        task_manager.complete_task(tid)
        assert task_manager.active_task_id is None
        completed_info = task_manager.get_task_status(tid)
        assert completed_info["task"]["status"] == "completed"

    def test_failure_and_cancellation(self, task_manager):
        t_fail = task_manager.create_task("Failing job")
        task_manager.fail_task(t_fail.task_id, "Selector not found")
        f_info = task_manager.get_task_status(t_fail.task_id)
        assert f_info["task"]["status"] == "failed"
        assert f_info["task"]["error_message"] == "Selector not found"

        t_cancel = task_manager.create_task("Cancelled job")
        task_manager.cancel_task(t_cancel.task_id)
        c_info = task_manager.get_task_status(t_cancel.task_id)
        assert c_info["task"]["status"] == "cancelled"

    def test_list_history(self, task_manager):
        for i in range(5):
            task_manager.create_task(f"Job {i}")
        history = task_manager.list_history(limit=3)
        assert len(history) == 3
        # Most recent first
        assert history[0]["description"] == "Job 4"
