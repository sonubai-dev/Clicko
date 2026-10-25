"""Autonomous execution runner coordinating multi-step task execution with verification."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable
import uuid

from local_computer_autopilot.agent.models import (
    ExecutionResult,
    PlanStep,
    StepExecutionDetail,
    TaskPlan,
)
from local_computer_autopilot.browser import BrowserManager
from local_computer_autopilot.computer.controller import ComputerController
from local_computer_autopilot.computer.safety import SafetyError
from local_computer_autopilot.config import AppConfig
from local_computer_autopilot.desktop import WindowManager
from local_computer_autopilot.execution.cancellation import CancellationToken
from local_computer_autopilot.execution.retry import retry_with_backoff, run_with_timeout
from local_computer_autopilot.macros.storage import MacroStorage
from local_computer_autopilot.scheduler.storage import ScheduleStorage
from local_computer_autopilot.task import StepStatus, TaskManager
from local_computer_autopilot.vision import locate_template, wait_for_visual_change

logger = logging.getLogger("local_computer_autopilot.agent.runner")

MAX_AGENT_STEPS = 25


class AutonomousAgent:
    """Executes planned workflows with visual verification, safety checks, and SQLite auditing."""

    def __init__(
        self,
        controller: ComputerController | None = None,
        task_manager: TaskManager | None = None,
        window_manager: WindowManager | None = None,
        browser_manager: BrowserManager | None = None,
        macro_storage: MacroStorage | None = None,
        schedule_storage: ScheduleStorage | None = None,
        cancellation_token: CancellationToken | None = None,
        config: AppConfig | None = None,
        require_approval: bool = False,
        approval_actions: set[str] | None = None,
        approval_callback: Callable[[dict[str, Any]], bool] | None = None,
        approval_timeout_seconds: float = 60.0,
    ) -> None:
        self.config = config or AppConfig()
        self.controller = controller or ComputerController(self.config)
        self.task_manager = task_manager or TaskManager()
        self.window_manager = window_manager or WindowManager()
        self.browser_manager = browser_manager or BrowserManager()
        self.macro_storage = macro_storage or MacroStorage()
        self.schedule_storage = schedule_storage or ScheduleStorage()
        self.cancellation_token = cancellation_token or CancellationToken()

        # Human-in-the-loop approval attributes
        self.require_approval = require_approval
        self.approval_actions = approval_actions or {"desktop_close_app"}
        self.approval_callback = approval_callback
        self.approval_timeout_seconds = approval_timeout_seconds
        self.pending_approvals: dict[str, dict[str, Any]] = {}
        self._approval_lock = threading.Lock()

    def get_pending_approvals(self) -> list[dict[str, Any]]:
        """List active approval requests awaiting human operator decision."""
        with self._approval_lock:
            return [
                {
                    "approval_id": app_id,
                    "task_id": data["task_id"],
                    "step": data["step"],
                    "created_at": data["created_at"],
                }
                for app_id, data in self.pending_approvals.items()
            ]

    def resolve_approval(self, approval_id: str, approved: bool) -> bool:
        """Resolve a pending human approval decision."""
        with self._approval_lock:
            if approval_id not in self.pending_approvals:
                return False
            data = self.pending_approvals[approval_id]
            data["approved"] = approved
            data["event"].set()
            return True

    def _request_approval(self, step: PlanStep, task_id: str) -> bool:
        """Request human approval before executing a sensitive step."""
        if self.approval_callback is not None:
            return self.approval_callback({"task_id": task_id, "step": step.model_dump()})

        approval_id = f"appr_{uuid.uuid4().hex[:8]}"
        event = threading.Event()
        with self._approval_lock:
            self.pending_approvals[approval_id] = {
                "event": event,
                "approved": None,
                "task_id": task_id,
                "step": step.model_dump(),
                "created_at": time.time(),
            }

        logger.info(
            "Step %d (%s) waiting for human approval (approval_id: %s)",
            step.step_number,
            step.action_name,
            approval_id,
        )

        try:
            # Wait for operator response, with cancellation token checking
            start = time.time()
            while (time.time() - start) < self.approval_timeout_seconds:
                if self.cancellation_token.is_cancelled:
                    return False
                if event.wait(timeout=0.5):
                    break

            with self._approval_lock:
                approved = bool(self.pending_approvals.get(approval_id, {}).get("approved", False))
            return approved
        finally:
            with self._approval_lock:
                self.pending_approvals.pop(approval_id, None)

    def run_plan(self, plan: TaskPlan, task_id: str | None = None) -> ExecutionResult:
        """Execute all steps in a TaskPlan sequentially."""
        start_time = time.time()
        task_record = self.task_manager.create_task(description=plan.goal, task_id=task_id)
        current_task_id = task_record.task_id

        logger.info("Agent starting task '%s' (%d steps)", current_task_id, len(plan.steps))
        step_details: list[StepExecutionDetail] = []
        completed_count = 0
        overall_error: str | None = None

        if len(plan.steps) > MAX_AGENT_STEPS:
            err = f"Plan exceeds maximum allowed steps limit ({len(plan.steps)} > {MAX_AGENT_STEPS})"
            self.task_manager.fail_task(current_task_id, err)
            return ExecutionResult(
                task_id=current_task_id,
                goal=plan.goal,
                success=False,
                status="failed",
                steps_total=len(plan.steps),
                steps_completed=0,
                duration_seconds=round(time.time() - start_time, 2),
                error_message=err,
                step_details=[],
            )

        for step in plan.steps:
            # 1. Cooperative cancellation check
            if self.cancellation_token.is_cancelled:
                overall_error = f"Aborted: {self.cancellation_token.reason}"
                self.task_manager.cancel_task(current_task_id)
                break

            step_start = time.time()
            step_success = False
            step_summary = ""
            step_error: str | None = None
            visual_verified = False

            # Capture baseline screenshot if visual verification is requested
            before_screenshot: bytes | None = None
            if step.verify_visual:
                try:
                    before_screenshot = self.controller.take_screenshot()
                except Exception as e:
                    logger.debug("Could not capture baseline screenshot: %s", e)

            try:
                # Check human approval requirement
                if self.require_approval or (self.approval_actions and step.action_name in self.approval_actions):
                    approved = self._request_approval(step, current_task_id)
                    if not approved:
                        raise SafetyError(
                            f"Step {step.step_number} ({step.action_name}) was rejected or timed out awaiting human approval"
                        )

                # 2. Execute action with bounded timeout & cancellation awareness
                def action_call() -> Any:
                    if self.cancellation_token.is_cancelled:
                        self.cancellation_token.check_cancelled()
                    return self._dispatch_action(step.action_name, step.parameters)

                result = run_with_timeout(
                    action_call,
                    timeout_seconds=step.timeout_seconds,
                    cancellation_token=self.cancellation_token,
                )
                step_success = True
                step_summary = f"Executed {step.action_name}: {str(result)[:100]}"

                # 3. Visual verification (if enabled)
                if step.verify_visual and before_screenshot:
                    try:
                        diff_res = wait_for_visual_change(
                            get_screenshot_fn=self.controller.take_screenshot,
                            before_bytes=before_screenshot,
                            threshold=0.01,
                            timeout=2.0,
                        )
                        visual_verified = diff_res.has_changed
                        step_summary += f" [Visual Change: {diff_res.diff_ratio:.1%}]"
                    except Exception as e:
                        logger.debug("Visual verification check error: %s", e)

            except Exception as e:
                step_success = False
                step_error = str(e)
                step_summary = f"Action failed: {step_error}"
                overall_error = f"Step {step.step_number} ({step.action_name}) failed: {step_error}"
                logger.error("Step execution error in step %d: %s", step.step_number, e)

            step_duration = round(time.time() - step_start, 2)

            # 4. Record step in SQLite audit database
            self.task_manager.record_step(
                task_id=current_task_id,
                action_name=step.action_name,
                parameters=step.parameters,
                status=StepStatus.SUCCESS if step_success else StepStatus.FAILED,
                result_summary=step_summary,
                error_message=step_error,
                visual_verified=visual_verified,
            )

            detail = StepExecutionDetail(
                step_number=step.step_number,
                action_name=step.action_name,
                parameters=step.parameters,
                status="success" if step_success else "failed",
                result_summary=step_summary,
                error_message=step_error,
                visual_verified=visual_verified,
                duration_seconds=step_duration,
            )
            step_details.append(detail)

            if step_success:
                completed_count += 1
            else:
                # Halt execution sequence on failure
                break

        total_duration = round(time.time() - start_time, 2)
        if self.cancellation_token.is_cancelled:
            self.task_manager.cancel_task(current_task_id)
            final_status = "cancelled"
            is_success = False
        elif overall_error:
            self.task_manager.fail_task(current_task_id, overall_error)
            final_status = "failed"
            is_success = False
        else:
            self.task_manager.complete_task(current_task_id)
            final_status = "completed"
            is_success = True

        return ExecutionResult(
            task_id=current_task_id,
            goal=plan.goal,
            success=is_success,
            status=final_status,
            steps_total=len(plan.steps),
            steps_completed=completed_count,
            duration_seconds=total_duration,
            error_message=overall_error,
            step_details=step_details,
        )

    def _dispatch_action(self, action_name: str, params: dict[str, Any]) -> Any:
        """Route action invocation to corresponding subsystem."""
        if not self.config.tool_policy.is_enabled(action_name):
            raise SafetyError(f"Tool '{action_name}' is disabled by policy")

        # Computer controller
        if action_name == "computer_get_screen_info":
            return self.controller.get_screen_info().model_dump()
        elif action_name == "computer_screenshot":
            return len(self.controller.take_screenshot())
        elif action_name == "computer_move_mouse":
            return self.controller.move_mouse(
                x=params.get("x", 0),
                y=params.get("y", 0),
                duration=params.get("duration", 0.5),
            ).model_dump()
        elif action_name == "computer_click":
            return self.controller.click(
                x=params.get("x", 0),
                y=params.get("y", 0),
                click_type=params.get("click_type", "left"),
            ).model_dump()
        elif action_name == "computer_scroll":
            return self.controller.scroll(
                clicks=params.get("clicks", 0),
                x=params.get("x"),
                y=params.get("y"),
                horizontal=params.get("horizontal", False),
            ).model_dump()
        elif action_name == "computer_type_text":
            return self.controller.type_text(params.get("text", "")).model_dump()
        elif action_name == "computer_press_key":
            return self.controller.press_key(params.get("key") or params.get("keys", "enter")).model_dump()
        elif action_name == "computer_get_status":
            return self.controller.get_status(["all"]).model_dump()

        # Desktop window manager
        elif action_name == "desktop_list_windows":
            return [w.model_dump() for w in self.window_manager.list_windows()]
        elif action_name == "desktop_focus_window":
            return self.window_manager.focus_window(params.get("query", "")).model_dump()
        elif action_name == "desktop_get_window_bounds":
            return self.window_manager.get_window_bounds(params.get("query", "")).model_dump()
        elif action_name == "desktop_set_window_state":
            return self.window_manager.set_window_state(params.get("query", ""), params.get("state", "normal")).model_dump()

        # Browser manager
        elif action_name == "browser_open":
            return self.browser_manager.open_url(params.get("url", "about:blank"), headless=params.get("headless", False)).model_dump()
        elif action_name == "browser_new_tab":
            return self.browser_manager.new_tab(params.get("url")).model_dump()
        elif action_name == "browser_list_tabs":
            return [t.model_dump() for t in self.browser_manager.list_tabs()]
        elif action_name == "browser_switch_tab":
            return self.browser_manager.switch_tab(int(params.get("tab_index", 0))).model_dump()
        elif action_name == "browser_close_tab":
            self.browser_manager.close_tab(params.get("tab_index"))
            return {"closed": True}
        elif action_name == "browser_click":
            return self.browser_manager.click(params.get("selector", "")).model_dump()
        elif action_name == "browser_type":
            return self.browser_manager.type_text(params.get("selector", ""), params.get("text", "")).model_dump()
        elif action_name == "browser_get_content":
            return self.browser_manager.get_content(params.get("selector")).model_dump()
        elif action_name == "browser_screenshot":
            return len(self.browser_manager.take_screenshot())
        elif action_name == "browser_close":
            self.browser_manager.close()
            return {"closed": True}

        # Phase 4: Multi-monitor display management
        elif action_name == "computer_get_monitors":
            return [m.model_dump() for m in self.controller.get_monitors()]

        # Phase 4: System clipboard
        elif action_name == "computer_clipboard_get":
            return self.controller.get_clipboard_text().model_dump()
        elif action_name == "computer_clipboard_set":
            return self.controller.set_clipboard_text(params.get("text", "")).model_dump()

        # Phase 4: Desktop application lifecycle
        elif action_name == "desktop_launch_app":
            return self.window_manager.launch_app(
                params.get("app_name", ""),
                args=params.get("args"),
                wait_seconds=params.get("wait_seconds", 2.0),
            ).model_dump()
        elif action_name == "desktop_close_app":
            return self.window_manager.close_app(
                params.get("query", ""),
                graceful=params.get("graceful", True),
            ).model_dump()

        # Phase 4: Visual template locate & click
        elif action_name == "visual_locate_element":
            haystack = self.controller.take_screenshot()
            bbox = None
            if "bbox" in params and params["bbox"]:
                from local_computer_autopilot.vision.models import BoundingBox
                bbox = BoundingBox(**params["bbox"])
            return locate_template(
                haystack_bytes=haystack,
                needle_source=params.get("template") or params.get("image", ""),
                bbox=bbox,
                confidence=params.get("confidence", 0.9),
            ).model_dump()
        elif action_name == "visual_click_element":
            haystack = self.controller.take_screenshot()
            bbox = None
            if "bbox" in params and params["bbox"]:
                from local_computer_autopilot.vision.models import BoundingBox
                bbox = BoundingBox(**params["bbox"])
            loc = locate_template(
                haystack_bytes=haystack,
                needle_source=params.get("template") or params.get("image", ""),
                bbox=bbox,
                confidence=params.get("confidence", 0.9),
            )
            if not loc.found or loc.x is None or loc.y is None:
                raise SafetyError(f"Could not locate template image to click: {loc.message}")
            click_res = self.controller.click(
                x=loc.x,
                y=loc.y,
                click_type=params.get("click_type", "left"),
            )
            return {
                "success": click_res.success,
                "x": loc.x,
                "y": loc.y,
                "click_type": params.get("click_type", "left"),
                "message": f"Clicked template at ({loc.x}, {loc.y})",
            }

        # Phase 4: Macros
        elif action_name == "macro_create":
            return self.macro_storage.create_macro(
                name=params.get("name", ""),
                description=params.get("description", ""),
                steps=params.get("steps", []),
                parameters=params.get("parameters", []),
            ).model_dump()
        elif action_name == "macro_list":
            return [m.model_dump() for m in self.macro_storage.list_macros()]
        elif action_name == "macro_execute":
            from local_computer_autopilot.macros.runner import MacroRunner
            runner = MacroRunner(self.macro_storage, self)
            return runner.execute_macro(
                params.get("identifier") or params.get("name") or params.get("macro_id", ""),
                parameters=params.get("parameters"),
            ).model_dump()
        elif action_name == "macro_delete":
            deleted = self.macro_storage.delete_macro(
                params.get("identifier") or params.get("name") or params.get("macro_id", "")
            )
            return {"deleted": deleted}

        # Phase 5: Production Automation Scheduler
        elif action_name == "schedule_create":
            sched = self.schedule_storage.create_schedule(
                name=params.get("name", ""),
                interval_seconds=int(params.get("interval_seconds", 60)),
                target=params.get("target", ""),
                is_macro=bool(params.get("is_macro", False)),
            )
            return sched.model_dump()
        elif action_name == "schedule_list":
            return [s.model_dump() for s in self.schedule_storage.list_schedules()]
        elif action_name == "schedule_delete":
            deleted = self.schedule_storage.delete_schedule(
                params.get("identifier") or params.get("id") or params.get("name", "")
            )
            return {"deleted": deleted}
        elif action_name == "schedule_toggle":
            updated = self.schedule_storage.toggle_schedule(
                params.get("identifier") or params.get("id") or params.get("name", ""),
                enabled=bool(params.get("enabled", True)),
            )
            return {"success": updated}

        # Phase 5: Compliance and task audit exports
        elif action_name == "audit_export_json":
            from local_computer_autopilot.audit.exporter import export_audit_json
            data = export_audit_json(
                self.task_manager.storage,
                task_id=params.get("task_id"),
                output_path=params.get("output_path"),
            )
            return {"success": True, "output_path": params.get("output_path"), "size": len(data)}
        elif action_name == "audit_export_csv":
            from local_computer_autopilot.audit.exporter import export_audit_csv
            data = export_audit_csv(
                self.task_manager.storage,
                output_path=params.get("output_path"),
            )
            return {"success": True, "output_path": params.get("output_path"), "size": len(data)}

        raise SafetyError(f"Unknown agent action: '{action_name}'")
