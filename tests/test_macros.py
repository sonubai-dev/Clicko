"""Unit tests for Macro storage, interpolation, and execution runner."""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from local_computer_autopilot.agent.runner import AutonomousAgent
from local_computer_autopilot.computer.safety import SafetyError
from local_computer_autopilot.config import AppConfig
from local_computer_autopilot.macros.models import MacroDefinition
from local_computer_autopilot.macros.runner import MacroRunner, interpolate_params
from local_computer_autopilot.macros.storage import MacroStorage
from local_computer_autopilot.task import TaskManager, TaskStorage


@pytest.fixture
def memory_macro_storage():
    return MacroStorage(db_path=":memory:")


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    mock_res = MagicMock()
    mock_res.success = True
    mock_res.steps_completed = 2
    mock_res.total_steps = 2
    mock_res.error_message = None
    mock_res.task_id = "task_test_123"
    agent.run_plan.return_value = mock_res
    return agent


class TestMacroStorage:
    def test_create_and_get_macro(self, memory_macro_storage: MacroStorage):
        steps = [
            {"tool": "browser_open", "args": {"url": "{{target_url}}"}},
            {"tool": "browser_click", "args": {"selector": "button#submit"}},
        ]
        created = memory_macro_storage.create_macro(
            name="Submit Form Macro",
            description="Opens URL and submits form",
            steps=steps,
            parameters=["target_url"],
        )
        assert created.id.startswith("macro_")
        assert created.name == "Submit Form Macro"
        assert len(created.steps) == 2

        # Fetch by ID
        fetched = memory_macro_storage.get_macro(created.id)
        assert fetched is not None
        assert fetched.name == "Submit Form Macro"
        assert fetched.parameters == ["target_url"]

        # Fetch by name
        fetched_name = memory_macro_storage.get_macro("Submit Form Macro")
        assert fetched_name is not None
        assert fetched_name.id == created.id

    def test_list_and_delete_macros(self, memory_macro_storage: MacroStorage):
        memory_macro_storage.create_macro("Macro A", "Desc A", [{"tool": "test"}])
        memory_macro_storage.create_macro("Macro B", "Desc B", [{"tool": "test"}])

        macros = memory_macro_storage.list_macros()
        assert len(macros) == 2

        # Delete Macro A
        deleted = memory_macro_storage.delete_macro("Macro A")
        assert deleted is True

        remaining = memory_macro_storage.list_macros()
        assert len(remaining) == 1
        assert remaining[0].name == "Macro B"


class TestMacroRunner:
    def test_parameter_interpolation(self):
        args = {
            "url": "https://example.com/search?q={{query}}",
            "count": 10,
            "nested": ["item_{id}"],
        }
        interpolated = interpolate_params(args, {"query": "python", "id": 42})
        assert interpolated["url"] == "https://example.com/search?q=python"
        assert interpolated["count"] == 10
        assert interpolated["nested"] == ["item_42"]

    def test_execute_macro_success(
        self, memory_macro_storage: MacroStorage, mock_agent: MagicMock
    ):
        steps = [
            {"tool": "browser_open", "args": {"url": "https://example.com/{{page}}"}}
        ]
        macro = memory_macro_storage.create_macro(
            "Open Example", "Navigates to page", steps, ["page"]
        )

        runner = MacroRunner(storage=memory_macro_storage, agent=mock_agent)
        result = runner.execute_macro(macro.id, parameters={"page": "docs"})

        assert result.success is True
        assert result.macro_id == macro.id
        assert result.steps_executed == 2
        mock_agent.run_plan.assert_called_once()
        called_plan = mock_agent.run_plan.call_args[0][0]
        assert called_plan.steps[0].parameters["url"] == "https://example.com/docs"

    def test_execute_nonexistent_macro_raises(
        self, memory_macro_storage: MacroStorage, mock_agent: MagicMock
    ):
        runner = MacroRunner(storage=memory_macro_storage, agent=mock_agent)
        with pytest.raises(SafetyError, match="not found"):
            runner.execute_macro("missing_macro_id")
