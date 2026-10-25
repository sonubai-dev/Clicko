"""Unit tests for Human-in-the-Loop approval workflows."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock
import pytest

from local_computer_autopilot.agent.models import AgentMode, PlanStep, TaskPlan
from local_computer_autopilot.agent.runner import AutonomousAgent
from local_computer_autopilot.computer.safety import SafetyError
from local_computer_autopilot.task import TaskManager, TaskStorage


@pytest.fixture
def mock_controller():
    controller = MagicMock()
    controller.get_screen_info.return_value.model_dump.return_value = {"width": 1920, "height": 1080}
    controller.take_screenshot.return_value = b"\x89PNG_TEST_BYTES"
    controller.click.return_value.model_dump.return_value = {"success": True}
    return controller


@pytest.fixture
def memory_task_manager():
    return TaskManager(storage=TaskStorage(db_path=":memory:"))


class TestHumanInTheLoopApproval:
    def test_approval_callback_approves(self, mock_controller, memory_task_manager):
        callback_called = False

        def approve_cb(req: dict) -> bool:
            nonlocal callback_called
            callback_called = True
            return True

        agent = AutonomousAgent(
            controller=mock_controller,
            task_manager=memory_task_manager,
            require_approval=True,
            approval_callback=approve_cb,
        )

        plan = TaskPlan(
            goal="Take Screenshot",
            mode_used=AgentMode.STRUCTURED,
            steps=[
                PlanStep(
                    step_number=1,
                    action_name="computer_screenshot",
                    description="Capture screen",
                )
            ],
        )

        result = agent.run_plan(plan)
        assert callback_called is True
        assert result.success is True
        assert result.steps_completed == 1

    def test_approval_callback_rejects(self, mock_controller, memory_task_manager):
        def reject_cb(req: dict) -> bool:
            return False

        agent = AutonomousAgent(
            controller=mock_controller,
            task_manager=memory_task_manager,
            require_approval=True,
            approval_callback=reject_cb,
        )

        plan = TaskPlan(
            goal="Take Screenshot",
            mode_used=AgentMode.STRUCTURED,
            steps=[
                PlanStep(
                    step_number=1,
                    action_name="computer_screenshot",
                    description="Capture screen",
                )
            ],
        )

        result = agent.run_plan(plan)
        assert result.success is False
        assert result.steps_completed == 0
        assert "rejected or timed out" in (result.error_message or "")

    def test_async_approval_queue_and_resolution(self, mock_controller, memory_task_manager):
        agent = AutonomousAgent(
            controller=mock_controller,
            task_manager=memory_task_manager,
            require_approval=True,
            approval_timeout_seconds=5.0,
        )

        plan = TaskPlan(
            goal="Test Async Approval",
            mode_used=AgentMode.STRUCTURED,
            steps=[
                PlanStep(
                    step_number=1,
                    action_name="computer_screenshot",
                    description="Take screenshot",
                )
            ],
        )

        # Thread to simulate operator approving after short delay
        def operator_resolver():
            for _ in range(50):
                time.sleep(0.1)
                pending = agent.get_pending_approvals()
                if pending:
                    appr_id = pending[0]["approval_id"]
                    agent.resolve_approval(appr_id, approved=True)
                    return

        t = threading.Thread(target=operator_resolver, daemon=True)
        t.start()

        result = agent.run_plan(plan)
        t.join(timeout=3.0)

        assert result.success is True
        assert result.steps_completed == 1
