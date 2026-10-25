"""Unit tests for Autonomous Workflow Planner and Execution Agent."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from local_computer_autopilot.agent.models import AgentMode, PlanStep, TaskPlan
from local_computer_autopilot.agent.planner import WorkflowPlanner
from local_computer_autopilot.agent.runner import AutonomousAgent, MAX_AGENT_STEPS
from local_computer_autopilot.execution.cancellation import CancellationToken
from local_computer_autopilot.task import TaskManager, TaskStorage


@pytest.fixture
def mock_controller():
    controller = MagicMock()
    controller.get_screen_info.return_value.model_dump.return_value = {"width": 1920, "height": 1080}
    controller.take_screenshot.return_value = b"\x89PNG_TEST_BYTES"
    controller.move_mouse.return_value.model_dump.return_value = {"success": True}
    controller.click.return_value.model_dump.return_value = {"success": True}
    controller.type_text.return_value.model_dump.return_value = {"success": True}
    controller.get_status.return_value.model_dump.return_value = {"runtime_active": True}
    return controller


@pytest.fixture
def memory_task_manager():
    storage = TaskStorage(db_path=":memory:")
    return TaskManager(storage=storage)


class TestWorkflowPlanner:
    def test_plan_empty_goal(self):
        planner = WorkflowPlanner()
        plan = planner.plan("")
        assert len(plan.steps) == 0
        assert plan.mode_used == AgentMode.STRUCTURED

    def test_plan_screenshot_workflow(self):
        planner = WorkflowPlanner()
        plan = planner.plan("take a screenshot of my screen")
        assert len(plan.steps) >= 2
        actions = [s.action_name for s in plan.steps]
        assert "computer_get_screen_info" in actions
        assert "computer_screenshot" in actions

    def test_plan_browser_search_workflow(self):
        planner = WorkflowPlanner()
        plan = planner.plan("open browser and search for python documentation")
        actions = [s.action_name for s in plan.steps]
        assert "browser_open" in actions
        assert "browser_type" in actions
        assert "computer_press_key" in actions
        assert "browser_screenshot" in actions

    def test_plan_window_list_workflow(self):
        planner = WorkflowPlanner()
        plan = planner.plan("list open windows on desktop")
        assert len(plan.steps) == 1
        assert plan.steps[0].action_name == "desktop_list_windows"

    def test_plan_type_text_workflow(self):
        planner = WorkflowPlanner()
        plan = planner.plan("type 'Hello World'")
        assert len(plan.steps) == 1
        assert plan.steps[0].action_name == "computer_type_text"
        assert plan.steps[0].parameters["text"] == "Hello World"

    def test_plan_click_coordinates(self):
        planner = WorkflowPlanner()
        plan = planner.plan("click at 350, 420")
        assert len(plan.steps) == 1
        assert plan.steps[0].action_name == "computer_click"
        assert plan.steps[0].parameters["x"] == 350
        assert plan.steps[0].parameters["y"] == 420

    def test_local_llm_fallback_when_offline(self):
        planner = WorkflowPlanner()
        with patch.object(planner, "is_local_llm_available", return_value=False):
            plan = planner.plan("take a screenshot", mode=AgentMode.LOCAL_LLM)
            assert plan.mode_used == AgentMode.STRUCTURED
            assert len(plan.steps) >= 1

    def test_local_llm_parsing_when_online(self):
        planner = WorkflowPlanner()
        mock_response = {
            "response": json.dumps({
                "steps": [
                    {
                        "action_name": "computer_screenshot",
                        "parameters": {},
                        "description": "Capture screen via LLM",
                        "verify_visual": False,
                    }
                ]
            })
        }
        with patch.object(planner, "is_local_llm_available", return_value=True), \
             patch("urllib.request.urlopen") as mock_url:
            mock_cm = MagicMock()
            mock_cm.read.return_value = json.dumps(mock_response).encode("utf-8")
            mock_cm.__enter__.return_value = mock_cm
            mock_url.return_value = mock_cm

            plan = planner.plan("capture screen", mode=AgentMode.LOCAL_LLM)
            assert plan.mode_used == AgentMode.LOCAL_LLM
            assert len(plan.steps) == 1
            assert plan.steps[0].action_name == "computer_screenshot"

    def test_local_llm_rejects_unrecognized_action(self):
        planner = WorkflowPlanner()
        mock_response = {
            "response": json.dumps({
                "steps": [
                    {
                        "action_name": "malicious_unregistered_hack",
                        "parameters": {},
                        "description": "Hallucinated unsafe action",
                    },
                    {
                        "action_name": "computer_screenshot",
                        "parameters": {},
                        "description": "Safe allowed action",
                    }
                ]
            })
        }
        with patch.object(planner, "is_local_llm_available", return_value=True), \
             patch("urllib.request.urlopen") as mock_url:
            mock_cm = MagicMock()
            mock_cm.read.return_value = json.dumps(mock_response).encode("utf-8")
            mock_cm.__enter__.return_value = mock_cm
            mock_url.return_value = mock_cm

            plan = planner.plan("capture screen", mode=AgentMode.LOCAL_LLM)
            assert plan.mode_used == AgentMode.LOCAL_LLM
            assert len(plan.steps) == 1
            assert plan.steps[0].action_name == "computer_screenshot"


class TestAutonomousAgent:
    def test_run_successful_plan(self, mock_controller, memory_task_manager):
        agent = AutonomousAgent(
            controller=mock_controller,
            task_manager=memory_task_manager,
        )
        plan = TaskPlan(
            goal="Inspect screen",
            mode_used=AgentMode.STRUCTURED,
            steps=[
                PlanStep(
                    step_number=1,
                    action_name="computer_get_screen_info",
                    parameters={},
                    description="Get screen resolution",
                    verify_visual=False,
                ),
                PlanStep(
                    step_number=2,
                    action_name="computer_screenshot",
                    parameters={},
                    description="Capture screenshot",
                    verify_visual=False,
                ),
            ],
        )

        result = agent.run_plan(plan)
        assert result.success is True
        assert result.status == "completed"
        assert result.steps_completed == 2
        assert len(result.step_details) == 2

        # Check SQLite record
        task_status = memory_task_manager.get_task_status(result.task_id)
        assert task_status["found"] is True
        assert task_status["task"]["status"] == "completed"
        assert len(task_status["steps"]) == 2

    def test_run_plan_with_step_failure(self, mock_controller, memory_task_manager):
        agent = AutonomousAgent(
            controller=mock_controller,
            task_manager=memory_task_manager,
        )
        plan = TaskPlan(
            goal="Run failing action",
            mode_used=AgentMode.STRUCTURED,
            steps=[
                PlanStep(
                    step_number=1,
                    action_name="non_existent_tool_action",
                    parameters={},
                    description="Invalid step",
                )
            ],
        )

        result = agent.run_plan(plan)
        assert result.success is False
        assert result.status == "failed"
        assert result.steps_completed == 0
        assert "disabled by policy" in result.error_message or "Unknown agent action" in result.error_message

    def test_run_plan_aborts_on_cancellation(self, mock_controller, memory_task_manager):
        token = CancellationToken()
        token.cancel("Emergency Stop active")
        agent = AutonomousAgent(
            controller=mock_controller,
            task_manager=memory_task_manager,
            cancellation_token=token,
        )
        plan = TaskPlan(
            goal="Should not run",
            mode_used=AgentMode.STRUCTURED,
            steps=[
                PlanStep(
                    step_number=1,
                    action_name="computer_get_screen_info",
                    parameters={},
                    description="Check screen",
                )
            ],
        )

        result = agent.run_plan(plan)
        assert result.success is False
        assert result.status == "cancelled"
        assert "Aborted" in result.error_message

    def test_exceeding_max_steps_guardrail(self, mock_controller, memory_task_manager):
        agent = AutonomousAgent(
            controller=mock_controller,
            task_manager=memory_task_manager,
        )
        oversized_steps = [
            PlanStep(step_number=i, action_name="computer_get_status", description=f"Step {i}")
            for i in range(1, MAX_AGENT_STEPS + 5)
        ]
        plan = TaskPlan(
            goal="Infinite loop attempt",
            mode_used=AgentMode.STRUCTURED,
            steps=oversized_steps,
        )

        result = agent.run_plan(plan)
        assert result.success is False
        assert result.status == "failed"
        assert "exceeds maximum allowed steps" in result.error_message

    def test_policy_enforcement_in_dispatch(self, mock_controller, memory_task_manager):
        from local_computer_autopilot.computer.safety import SafetyError
        agent = AutonomousAgent(
            controller=mock_controller,
            task_manager=memory_task_manager,
        )
        agent.config.tool_policy.computer_click = False

        with pytest.raises(SafetyError, match="disabled by policy"):
            agent._dispatch_action("computer_click", {"x": 100, "y": 100})
