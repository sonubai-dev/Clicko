"""MCP server exposing safe computer-control and automation tools via stdio transport."""

from __future__ import annotations

import logging
import sys

from mcp.server.mcpserver import Image, MCPServer

from local_computer_autopilot.agent import AgentMode, AutonomousAgent, WorkflowPlanner
from local_computer_autopilot.audit import export_audit_csv, export_audit_json
from local_computer_autopilot.browser import BrowserManager
from local_computer_autopilot.computer.controller import ComputerController
from local_computer_autopilot.computer.safety import SafetyError
from local_computer_autopilot.config import AppConfig, configure_logging
from local_computer_autopilot.desktop import WindowManager
from local_computer_autopilot.execution import CancellationToken
from local_computer_autopilot.macros import MacroRunner, MacroStorage
from local_computer_autopilot.scheduler import ScheduleStorage, WorkflowScheduler
from local_computer_autopilot.task import StepStatus, TaskManager
from local_computer_autopilot.vision import BoundingBox, locate_template, wait_for_visual_change

# ── Subsystem Initialization ───────────────────────────────────────────────

_config = AppConfig()
_logger = configure_logging(_config.log_level)
_controller = ComputerController(_config)
_policy = _config.tool_policy

_task_manager = TaskManager()
_window_manager = WindowManager()
_browser_manager = BrowserManager()
_macro_storage = MacroStorage()
_schedule_storage = ScheduleStorage()
_cancellation_token = CancellationToken()
_planner = WorkflowPlanner()
_agent = AutonomousAgent(
    controller=_controller,
    task_manager=_task_manager,
    window_manager=_window_manager,
    browser_manager=_browser_manager,
    macro_storage=_macro_storage,
    schedule_storage=_schedule_storage,
    cancellation_token=_cancellation_token,
    config=_config,
)
_macro_runner = MacroRunner(_macro_storage, _agent)
_workflow_scheduler = WorkflowScheduler(
    storage=_schedule_storage,
    agent=_agent,
    planner=_planner,
    macro_runner=_macro_runner,
)

# ── MCP Server ─────────────────────────────────────────────────────────────

mcp = MCPServer(
    name="LocalComputerAutopilot",
    instructions=(
        "Clicko / LocalComputerAutopilot: A safe, local-first computer control and automation server. "
        "Interact with Windows desktop (mouse, keyboard, windows), local browsers (Edge/Chrome), "
        "verify visual changes, and track tasks. Move mouse to screen corner to emergency abort."
    ),
)


def _check_policy(tool_name: str) -> None:
    """Raise SafetyError if the tool is disabled by policy."""
    if not _policy.is_enabled(tool_name):
        raise SafetyError(f"Tool '{tool_name}' is disabled by policy")


# ── Phase 1: Computer Control Tools ────────────────────────────────────────


@mcp.tool()
def computer_get_screen_info() -> dict:
    """Get the current screen dimensions (width and height in pixels)."""
    _check_policy("computer_get_screen_info")
    info = _controller.get_screen_info()
    return info.model_dump()


@mcp.tool()
def computer_screenshot() -> Image:
    """Capture a screenshot of the entire screen.

    Returns the screenshot as a PNG image. The image is NOT saved to disk.
    Only call this tool when you explicitly need to inspect the screen.
    """
    _check_policy("computer_screenshot")
    png_bytes = _controller.take_screenshot()
    return Image(data=png_bytes, format="png")


@mcp.tool()
def computer_move_mouse(x: int, y: int, duration: float = 0.5) -> dict:
    """Move the mouse cursor to the specified screen coordinates.

    Args:
        x: Target x coordinate (0 = left edge).
        y: Target y coordinate (0 = top edge).
        duration: Movement duration in seconds (0.0 to 5.0). Default 0.5.
    """
    _check_policy("computer_move_mouse")
    result = _controller.move_mouse(x, y, duration)
    return result.model_dump()


@mcp.tool()
def computer_click(x: int, y: int, click_type: str = "left") -> dict:
    """Perform a mouse click at the specified coordinates.

    Args:
        x: Target x coordinate.
        y: Target y coordinate.
        click_type: Type of click — 'left', 'right', 'middle', or 'double'.
    """
    _check_policy("computer_click")
    result = _controller.click(x, y, click_type)
    return result.model_dump()


@mcp.tool()
def computer_scroll(
    clicks: int,
    x: int | None = None,
    y: int | None = None,
    horizontal: bool = False,
) -> dict:
    """Scroll the mouse wheel.

    Args:
        clicks: Number of scroll increments. Positive = up/right, negative = down/left. Max ±20.
        x: Optional x coordinate to scroll at.
        y: Optional y coordinate to scroll at.
        horizontal: If true, scroll horizontally instead of vertically.
    """
    _check_policy("computer_scroll")
    result = _controller.scroll(clicks, x=x, y=y, horizontal=horizontal)
    return result.model_dump()


@mcp.tool()
def computer_type_text(text: str) -> dict:
    """Type text using the keyboard.

    The text content is never logged for privacy. Maximum 1000 characters.

    Args:
        text: The text to type.
    """
    _check_policy("computer_type_text")
    result = _controller.type_text(text)
    return result.model_dump()


@mcp.tool()
def computer_press_key(key: str | None = None, keys: list[str] | None = None) -> dict:
    """Press a single key or a key combination.

    Provide either 'key' for a single keypress, or 'keys' for a combination.

    Args:
        key: A single key name, e.g. 'enter', 'tab', 'f5'.
        keys: A list of keys for a combination, e.g. ['ctrl', 's'].
    """
    _check_policy("computer_press_key")
    if key is not None and keys is not None:
        raise SafetyError("Provide either 'key' or 'keys', not both")
    if key is not None:
        result = _controller.press_key(key)
    elif keys is not None:
        result = _controller.press_key(keys)
    else:
        raise SafetyError("Must provide either 'key' (single key) or 'keys' (combination)")
    return result.model_dump()


@mcp.tool()
def computer_get_status() -> dict:
    """Get the current runtime status including safety state and enabled tools."""
    _check_policy("computer_get_status")
    all_tool_names = [
        "computer_get_screen_info",
        "computer_screenshot",
        "computer_move_mouse",
        "computer_click",
        "computer_scroll",
        "computer_type_text",
        "computer_press_key",
        "computer_get_status",
        "visual_wait_for_change",
        "task_create",
        "task_record_step",
        "task_get_status",
        "task_list_history",
        "task_cancel",
        "desktop_list_windows",
        "desktop_focus_window",
        "desktop_get_window_bounds",
        "desktop_set_window_state",
        "browser_open",
        "browser_new_tab",
        "browser_list_tabs",
        "browser_switch_tab",
        "browser_close_tab",
        "browser_click",
        "browser_type",
        "browser_get_content",
        "browser_screenshot",
        "browser_close",
        "agent_plan_task",
        "agent_execute_task",
        "web_get_status",
    ]
    enabled = [name for name in all_tool_names if _policy.is_enabled(name)]
    status = _controller.get_status(enabled)
    return status.model_dump()


# ── Phase 2: Visual Verification Tools ─────────────────────────────────────


@mcp.tool()
def visual_wait_for_change(
    timeout: float = 3.0,
    x: int | None = None,
    y: int | None = None,
    width: int | None = None,
    height: int | None = None,
    threshold: float = 0.01,
) -> dict:
    """Wait and verify whether a visual change occurred on screen or in a region.

    Takes a baseline screenshot immediately, then polls until changes exceed threshold.

    Args:
        timeout: Maximum seconds to wait (0.5 to 10.0s).
        x: Optional bounding box left coordinate.
        y: Optional bounding box top coordinate.
        width: Optional bounding box width.
        height: Optional bounding box height.
        threshold: Fractional threshold of changed pixels (0.001 to 0.5). Default 0.01 (1%).
    """
    _check_policy("visual_wait_for_change")
    bbox = None
    if x is not None and y is not None and width is not None and height is not None:
        bbox = BoundingBox(x=x, y=y, width=width, height=height)

    # Capture initial baseline
    before_bytes = _controller.take_screenshot()
    result = wait_for_visual_change(
        get_screenshot_fn=_controller.take_screenshot,
        before_bytes=before_bytes,
        bbox=bbox,
        threshold=max(0.001, min(0.5, threshold)),
        timeout=max(0.5, min(10.0, timeout)),
    )
    return result.model_dump()


# ── Phase 2: Task Tracking Tools ───────────────────────────────────────────


@mcp.tool()
def task_create(description: str, task_id: str | None = None) -> dict:
    """Start tracking a new task session with local SQLite history.

    Args:
        description: High-level description of what the task aims to achieve.
        task_id: Optional custom identifier. Auto-generated if omitted.
    """
    _check_policy("task_create")
    task = _task_manager.create_task(description=description, task_id=task_id)
    return task.model_dump()


@mcp.tool()
def task_record_step(
    task_id: str,
    action_name: str,
    parameters: dict | None = None,
    status: str = "success",
    result_summary: str | None = None,
    error_message: str | None = None,
    visual_verified: bool = False,
) -> dict:
    """Record an executed action step within a tracked task.

    Args:
        task_id: Target task ID.
        action_name: Name of tool or action performed (e.g. 'computer_click').
        parameters: Inputs supplied to the action (masked as appropriate).
        status: Status of the step ('pending', 'running', 'success', 'failed').
        result_summary: Brief note summarizing outcome.
        error_message: Error details if action failed.
        visual_verified: Whether visual confirmation was verified.
    """
    _check_policy("task_record_step")
    try:
        step_status = StepStatus(status.lower())
    except ValueError:
        step_status = StepStatus.SUCCESS

    step = _task_manager.record_step(
        task_id=task_id,
        action_name=action_name,
        parameters=parameters or {},
        status=step_status,
        result_summary=result_summary,
        error_message=error_message,
        visual_verified=visual_verified,
    )
    return step.model_dump()


@mcp.tool()
def task_get_status(task_id: str) -> dict:
    """Retrieve full audit history and current status for a task.

    Args:
        task_id: Task identifier to inspect.
    """
    _check_policy("task_get_status")
    return _task_manager.get_task_status(task_id)


@mcp.tool()
def task_list_history(limit: int = 10) -> list[dict]:
    """List recent task execution sessions from local SQLite history.

    Args:
        limit: Maximum number of records to return (1 to 50).
    """
    _check_policy("task_list_history")
    bounded_limit = max(1, min(50, limit))
    return _task_manager.list_history(limit=bounded_limit)


@mcp.tool()
def task_cancel(task_id: str) -> dict:
    """Cancel a task and trigger runtime cancellation token.

    Args:
        task_id: Task to cancel.
    """
    _check_policy("task_cancel")
    _task_manager.cancel_task(task_id)
    _cancellation_token.cancel(f"Task {task_id} cancelled by user request")
    return {"cancelled": True, "task_id": task_id}


# ── Phase 2: Desktop Window Navigation Tools ───────────────────────────────


@mcp.tool()
def desktop_list_windows() -> list[dict]:
    """List all open, visible top-level application windows with coordinates and titles."""
    _check_policy("desktop_list_windows")
    windows = _window_manager.list_windows()
    return [w.model_dump() for w in windows]


@mcp.tool()
def desktop_focus_window(query: str) -> dict:
    """Bring an application window to the foreground by title or handle.

    Args:
        query: Window title (or unique substring) or integer window handle.
    """
    _check_policy("desktop_focus_window")
    q: str | int = int(query) if query.isdigit() else query
    win = _window_manager.focus_window(q)
    return win.model_dump()


@mcp.tool()
def desktop_get_window_bounds(query: str) -> dict:
    """Get screen coordinates and dimensions for a window.

    Args:
        query: Window title (or unique substring) or integer window handle.
    """
    _check_policy("desktop_get_window_bounds")
    q: str | int = int(query) if query.isdigit() else query
    win = _window_manager.get_window_bounds(q)
    return win.model_dump()


@mcp.tool()
def desktop_set_window_state(query: str, state: str) -> dict:
    """Change window state (maximize, minimize, restore, normal).

    Args:
        query: Window title or handle.
        state: Desired state ('maximize', 'minimize', 'restore', 'normal').
    """
    _check_policy("desktop_set_window_state")
    q: str | int = int(query) if query.isdigit() else query
    win = _window_manager.set_window_state(q, state)
    return win.model_dump()


# ── Phase 2: Browser Automation Tools ──────────────────────────────────────


@mcp.tool()
def browser_open(url: str, headless: bool = False) -> dict:
    """Launch or navigate local browser to the specified URL.

    Uses installed Microsoft Edge or Google Chrome without external cloud dependencies.

    Args:
        url: Web address to visit (e.g. 'https://www.google.com').
        headless: If True, runs in background without visible window. Default False.
    """
    _check_policy("browser_open")
    state = _browser_manager.open_url(url, headless=headless)
    return state.model_dump()


@mcp.tool()
def browser_new_tab(url: str | None = None) -> dict:
    """Open a new browser tab and optionally navigate to a URL.

    Args:
        url: Optional URL to open in the new tab.
    """
    _check_policy("browser_new_tab")
    tab = _browser_manager.new_tab(url)
    return tab.model_dump()


@mcp.tool()
def browser_list_tabs() -> list[dict]:
    """List all open tabs in the current browser session."""
    _check_policy("browser_list_tabs")
    tabs = _browser_manager.list_tabs()
    return [t.model_dump() for t in tabs]


@mcp.tool()
def browser_switch_tab(tab_index: int) -> dict:
    """Switch focus to a specific tab by zero-based index.

    Args:
        tab_index: Tab index to focus.
    """
    _check_policy("browser_switch_tab")
    tab = _browser_manager.switch_tab(tab_index)
    return tab.model_dump()


@mcp.tool()
def browser_close_tab(tab_index: int | None = None) -> dict:
    """Close a specific tab or the current active tab.

    Args:
        tab_index: Optional tab index. Closes active tab if omitted.
    """
    _check_policy("browser_close_tab")
    _browser_manager.close_tab(tab_index)
    return {"closed": True, "remaining_tabs": len(_browser_manager.list_tabs())}


@mcp.tool()
def browser_click(selector: str) -> dict:
    """Click an element on the active browser page.

    Args:
        selector: CSS selector or XPath (e.g. 'button#submit', 'a.nav-link').
    """
    _check_policy("browser_click")
    res = _browser_manager.click(selector)
    return res.model_dump()


@mcp.tool()
def browser_type(selector: str, text: str) -> dict:
    """Type text into an input field on the active browser page.

    The text content is never logged for security.

    Args:
        selector: CSS selector for the input element.
        text: Text string to enter.
    """
    _check_policy("browser_type")
    res = _browser_manager.type_text(selector, text)
    return res.model_dump()


@mcp.tool()
def browser_get_content(selector: str | None = None) -> dict:
    """Retrieve text content from page body or a specific element.

    Args:
        selector: Optional CSS selector to inspect. Defaults to entire page body.
    """
    _check_policy("browser_get_content")
    res = _browser_manager.get_content(selector)
    return res.model_dump()


@mcp.tool()
def browser_screenshot() -> Image:
    """Take a screenshot of the active browser viewport."""
    _check_policy("browser_screenshot")
    png_bytes = _browser_manager.take_screenshot()
    return Image(data=png_bytes, format="png")


@mcp.tool()
def browser_close() -> dict:
    """Close the current local browser session completely."""
    _check_policy("browser_close")
    _browser_manager.close()
    return {"closed": True}


# ── Phase 3: Autonomous Agent & Web UI Tools ───────────────────────────────


@mcp.tool()
def agent_plan_task(goal: str, mode: str = "auto") -> dict:
    """Generate and inspect an execution plan for a goal without running it.

    Args:
        goal: High-level goal or action description.
        mode: Planning mode — 'auto' (checks local LLM then falls back to rules), 'local_llm', or 'structured'.
    """
    _check_policy("agent_plan_task")
    m = AgentMode(mode.lower()) if mode.lower() in [x.value for x in AgentMode] else AgentMode.AUTO
    plan = _planner.plan(goal, mode=m)
    return plan.model_dump()


@mcp.tool()
def agent_execute_task(goal: str, mode: str = "auto") -> dict:
    """Execute an autonomous multi-step workflow for a goal with visual verification.

    Args:
        goal: High-level goal description to accomplish.
        mode: Planning mode — 'auto', 'local_llm', or 'structured'.
    """
    _check_policy("agent_execute_task")
    m = AgentMode(mode.lower()) if mode.lower() in [x.value for x in AgentMode] else AgentMode.AUTO
    if _cancellation_token.is_cancelled:
        _cancellation_token.reset()
    plan = _planner.plan(goal, mode=m)
    result = _agent.run_plan(plan)
    return result.model_dump()


@mcp.tool()
def web_get_status() -> dict:
    """Get the Clicko Web UI dashboard status, URL, and launch instructions."""
    _check_policy("web_get_status")
    return {
        "dashboard_url": "http://127.0.0.1:8000",
        "features": [
            "Live Desktop Screen Viewer",
            "Emergency Stop Button",
            "SQLite Task Audit Log",
            "Autonomous Task Runner",
            "Interactive Tool Console",
            "Macro Workflow Engine",
            "Multi-Monitor Support",
            "Human-in-the-Loop Approvals",
        ],
        "launch_command": ".\\.venv\\Scripts\\python.exe -m local_computer_autopilot.web",
    }


# ── Phase 4: Visual Grounding, Macros, Multi-Monitor & Desktop Lifecycle ──


@mcp.tool()
def computer_get_monitors() -> list[dict]:
    """List all connected physical and virtual display monitors with bounds and work areas."""
    _check_policy("computer_get_monitors")
    monitors = _controller.get_monitors()
    return [m.model_dump() for m in monitors]


@mcp.tool()
def computer_clipboard_get() -> dict:
    """Safely inspect textual content currently stored on the Windows clipboard."""
    _check_policy("computer_clipboard_get")
    res = _controller.get_clipboard_text()
    return res.model_dump()


@mcp.tool()
def computer_clipboard_set(text: str) -> dict:
    """Safely copy text onto the Windows system clipboard (max 5000 chars)."""
    _check_policy("computer_clipboard_set")
    res = _controller.set_clipboard_text(text)
    return res.model_dump()


@mcp.tool()
def desktop_launch_app(
    app_name: str,
    args: list[str] | None = None,
    wait_seconds: float = 2.0,
) -> dict:
    """Launch a Windows application safely without shell execution.

    Args:
        app_name: Executable name or path (e.g. 'notepad', 'calc', 'mspaint').
        args: Optional list of argument strings.
        wait_seconds: Seconds to wait for application window discovery.
    """
    _check_policy("desktop_launch_app")
    res = _window_manager.launch_app(app_name, args=args, wait_seconds=wait_seconds)
    return res.model_dump()


@mcp.tool()
def desktop_close_app(query: str, graceful: bool = True) -> dict:
    """Close an application window gracefully via WM_CLOSE or process termination.

    Args:
        query: Window handle or window title substring.
        graceful: If True, sends WM_CLOSE allowing app to save and close cleanly.
    """
    _check_policy("desktop_close_app")
    # Support numeric handle strings
    q_val: str | int = int(query) if query.isdigit() else query
    res = _window_manager.close_app(q_val, graceful=graceful)
    return res.model_dump()


@mcp.tool()
def visual_locate_element(
    template: str,
    bbox: dict | None = None,
    confidence: float = 0.9,
) -> dict:
    """Locate an icon or UI element template on screen.

    Args:
        template: File path, base64 string, or bytes of the template image to find.
        bbox: Optional search region {'x': 0, 'y': 0, 'width': 100, 'height': 100}.
        confidence: Match confidence threshold (0.1 to 1.0).
    """
    _check_policy("visual_locate_element")
    haystack_bytes = _controller.take_screenshot()
    box_model = BoundingBox(**bbox) if bbox else None
    res = locate_template(haystack_bytes, template, bbox=box_model, confidence=confidence)
    return res.model_dump()


@mcp.tool()
def visual_click_element(
    template: str,
    click_type: str = "left",
    bbox: dict | None = None,
    confidence: float = 0.9,
) -> dict:
    """Locate a template on screen and click its center point.

    Args:
        template: File path or base64 string of the icon/button image.
        click_type: Mouse click type ('left', 'right', 'double').
        bbox: Optional search sub-region.
        confidence: Match confidence threshold.
    """
    _check_policy("visual_click_element")
    haystack_bytes = _controller.take_screenshot()
    box_model = BoundingBox(**bbox) if bbox else None
    loc = locate_template(haystack_bytes, template, bbox=box_model, confidence=confidence)
    if not loc.found or loc.x is None or loc.y is None:
        raise SafetyError(f"Could not locate template image to click: {loc.message}")

    click_res = _controller.click(loc.x, loc.y, click_type=click_type)
    return {
        "success": click_res.success,
        "x": loc.x,
        "y": loc.y,
        "click_type": click_type,
        "message": f"Clicked template at ({loc.x}, {loc.y})",
    }


@mcp.tool()
def macro_create(
    name: str,
    description: str,
    steps: list[dict],
    parameters: list[str] | None = None,
) -> dict:
    """Save a reusable parameterized macro workflow.

    Args:
        name: Unique name for the macro.
        description: Explains what the macro accomplishes.
        steps: List of action step objects (e.g. [{'tool': 'browser_open', 'args': {'url': '{{url}}'}}]).
        parameters: Optional list of parameter names to interpolate during execution.
    """
    _check_policy("macro_create")
    macro = _macro_storage.create_macro(name, description, steps, parameters=parameters)
    return macro.model_dump()


@mcp.tool()
def macro_list() -> list[dict]:
    """List all saved automation macros."""
    _check_policy("macro_list")
    macros = _macro_storage.list_macros()
    return [m.model_dump() for m in macros]


@mcp.tool()
def macro_execute(identifier: str, parameters: dict | None = None) -> dict:
    """Execute a saved macro workflow with optional parameter values.

    Args:
        identifier: Macro name or unique ID.
        parameters: Dictionary of variable values (e.g. {'url': 'https://example.com'}).
    """
    _check_policy("macro_execute")
    if _cancellation_token.is_cancelled:
        _cancellation_token.reset()
    runner = MacroRunner(_macro_storage, _agent)
    res = runner.execute_macro(identifier, parameters=parameters)
    return res.model_dump()


@mcp.tool()
def macro_delete(identifier: str) -> dict:
    """Delete a saved macro workflow.

    Args:
        identifier: Macro name or unique ID to delete.
    """
    _check_policy("macro_delete")
    deleted = _macro_storage.delete_macro(identifier)
    return {"deleted": deleted, "identifier": identifier}


# ── Phase 5: Production Automation Scheduler & Audit Exports ──────────────


@mcp.tool()
def schedule_create(
    name: str,
    interval_seconds: int,
    target: str,
    is_macro: bool = False,
) -> dict:
    """Create an automated recurring workflow schedule.

    Args:
        name: Unique descriptive name for the schedule.
        interval_seconds: Execution frequency in seconds (minimum 5s).
        target: Natural language goal or macro name to execute.
        is_macro: True if target refers to a saved macro, False for an autonomous goal.
    """
    _check_policy("schedule_create")
    if interval_seconds < 5:
        raise SafetyError("Schedule interval must be at least 5 seconds")
    sched = _schedule_storage.create_schedule(
        name=name,
        interval_seconds=interval_seconds,
        target=target,
        is_macro=is_macro,
    )
    return sched.model_dump()


@mcp.tool()
def schedule_list() -> list[dict]:
    """List all registered recurring automation schedules."""
    _check_policy("schedule_list")
    schedules = _schedule_storage.list_schedules()
    return [s.model_dump() for s in schedules]


@mcp.tool()
def schedule_delete(identifier: str) -> dict:
    """Delete a recurring automation schedule by ID or name.

    Args:
        identifier: Schedule unique ID or name.
    """
    _check_policy("schedule_delete")
    deleted = _schedule_storage.delete_schedule(identifier)
    return {"deleted": deleted, "identifier": identifier}


@mcp.tool()
def schedule_toggle(identifier: str, enabled: bool) -> dict:
    """Enable or disable a recurring automation schedule.

    Args:
        identifier: Schedule unique ID or name.
        enabled: True to activate schedule, False to pause it.
    """
    _check_policy("schedule_toggle")
    updated = _schedule_storage.toggle_schedule(identifier, enabled)
    return {"success": updated, "identifier": identifier, "enabled": enabled}


@mcp.tool()
def audit_export_json(task_id: str | None = None, output_path: str | None = None) -> dict:
    """Export task history and execution step audits to JSON format.

    Args:
        task_id: Optional task ID to export a single task. If omitted, exports recent tasks.
        output_path: Optional file path to write export into.
    """
    _check_policy("audit_export_json")
    json_str = export_audit_json(_task_manager.storage, task_id=task_id, output_path=output_path)
    import json as _json
    parsed = _json.loads(json_str)
    count = 1 if task_id else len(parsed.get("tasks", []))
    return {
        "success": True,
        "output_path": output_path,
        "task_count": count,
        "json_preview": json_str[:500] if not output_path else None,
    }


@mcp.tool()
def audit_export_csv(output_path: str | None = None) -> dict:
    """Export flattened task steps to CSV for spreadsheet audit inspection.

    Args:
        output_path: Optional file path to write export into.
    """
    _check_policy("audit_export_csv")
    csv_str = export_audit_csv(_task_manager.storage, output_path=output_path)
    return {
        "success": True,
        "output_path": output_path,
        "csv_preview": csv_str[:500] if not output_path else None,
    }


# ── Entry point ────────────────────────────────────────────────────────────


def main() -> None:
    """Launch the MCP server on stdio transport."""
    _logger.info("Starting LocalComputerAutopilot MCP server (stdio transport)")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
