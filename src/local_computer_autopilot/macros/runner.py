"""Macro execution coordinator using AutonomousAgent."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from local_computer_autopilot.agent.models import AgentMode, PlanStep, TaskPlan
from local_computer_autopilot.computer.safety import SafetyError
from local_computer_autopilot.macros.models import MacroDefinition, MacroExecutionResult
from local_computer_autopilot.macros.storage import MacroStorage

if TYPE_CHECKING:
    from local_computer_autopilot.agent.runner import AutonomousAgent

logger = logging.getLogger("local_computer_autopilot.macros")


def interpolate_params(val: Any, params: dict[str, Any]) -> Any:
    """Recursively replace {{param}} or {param} placeholders in arguments."""
    if isinstance(val, str):
        result = val
        for k, v in params.items():
            pattern_mustache = f"{{{{{k}}}}}"
            pattern_single = f"{{{k}}}"
            result = result.replace(pattern_mustache, str(v)).replace(pattern_single, str(v))
        return result
    elif isinstance(val, list):
        return [interpolate_params(item, params) for item in val]
    elif isinstance(val, dict):
        return {k: interpolate_params(v, params) for k, v in val.items()}
    return val


class MacroRunner:
    """Executes parameterized macros through the AutonomousAgent runtime."""

    def __init__(self, storage: MacroStorage, agent: AutonomousAgent) -> None:
        self.storage = storage
        self.agent = agent

    def execute_macro(
        self,
        identifier: str,
        parameters: dict[str, Any] | None = None,
    ) -> MacroExecutionResult:
        """Execute a saved macro with optional parameter substitution."""
        macro = self.storage.get_macro(identifier)
        if not macro:
            raise SafetyError(f"Macro '{identifier}' not found")

        params = parameters or {}
        raw_steps = macro.steps
        plan_steps: list[PlanStep] = []

        for idx, step_dict in enumerate(raw_steps):
            action_name = step_dict.get("tool") or step_dict.get("action")
            if not action_name:
                raise SafetyError(f"Step {idx + 1} of macro '{macro.name}' is missing 'tool' or 'action' name")

            raw_args = step_dict.get("args") or step_dict.get("params") or {}
            interpolated_args = interpolate_params(raw_args, params)
            desc = step_dict.get("description") or f"Execute {action_name}"

            plan_steps.append(
                PlanStep(
                    step_number=idx + 1,
                    action_name=action_name,
                    parameters=interpolated_args,
                    description=desc,
                )
            )

        mode_used = getattr(self.agent, "mode", AgentMode.STRUCTURED)
        if not isinstance(mode_used, AgentMode):
            try:
                mode_used = AgentMode(str(mode_used))
            except Exception:
                mode_used = AgentMode.STRUCTURED

        plan = TaskPlan(
            goal=f"Execute Macro: {macro.name}",
            mode_used=mode_used,
            steps=plan_steps,
        )

        logger.info("Running macro '%s' (%s) with %d steps", macro.name, macro.id, len(plan_steps))
        exec_res = self.agent.run_plan(plan)

        return MacroExecutionResult(
            macro_id=macro.id,
            name=macro.name,
            success=exec_res.success,
            steps_executed=exec_res.steps_completed,
            total_steps=getattr(exec_res, "steps_total", getattr(exec_res, "total_steps", len(plan_steps))),
            error_message=exec_res.error_message,
            task_id=exec_res.task_id,
        )
