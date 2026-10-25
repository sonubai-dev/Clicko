"""Tests for MCP tool registration and invocation.

Uses a module-scoped fixture to mock PyAutoGUI and import the server once.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import namedtuple
from unittest.mock import MagicMock

import pytest

Size = namedtuple("Size", ["width", "height"])


def _make_mock_pyautogui() -> MagicMock:
    import io
    from PIL import Image
    valid_img = Image.new("RGB", (100, 100), color=(128, 128, 128))
    buf = io.BytesIO()
    valid_img.save(buf, format="PNG")
    valid_png_bytes = buf.getvalue()

    mock_pag = MagicMock()
    mock_pag.size.return_value = Size(1920, 1080)
    mock_pag.FAILSAFE = True
    mock_pag.PAUSE = 0.1
    mock_image = MagicMock()
    mock_image.save = MagicMock(side_effect=lambda buf, format: buf.write(valid_png_bytes))
    mock_pag.screenshot.return_value = mock_image
    return mock_pag


@pytest.fixture(scope="module")
def mcp_server():
    """Set up a mocked PyAutoGUI and import the MCP server module.

    This fixture is scoped to this module to avoid contaminating
    other test modules.
    """
    mock_pag = _make_mock_pyautogui()

    # Temporarily replace pyautogui in sys.modules
    original_pyautogui = sys.modules.get("pyautogui")

    # Remove cached local_computer_autopilot modules so they reimport with our mock
    cached = {k: sys.modules.pop(k) for k in list(sys.modules) if k.startswith("local_computer_autopilot")}

    sys.modules["pyautogui"] = mock_pag

    import local_computer_autopilot.server as srv

    yield srv, mock_pag

    # Restore original modules
    for k in list(sys.modules):
        if k.startswith("local_computer_autopilot"):
            del sys.modules[k]
    sys.modules.update(cached)
    if original_pyautogui is not None:
        sys.modules["pyautogui"] = original_pyautogui
    elif "pyautogui" in sys.modules and sys.modules["pyautogui"] is mock_pag:
        del sys.modules["pyautogui"]


# ── Tool registration ─────────────────────────────────────────────────────


class TestToolRegistration:
    def test_all_tools_registered(self, mcp_server):
        srv, _ = mcp_server
        tools = asyncio.run(srv.mcp.list_tools())
        tool_names = {t.name for t in tools}
        expected = {
            # Phase 1: Computer controls
            "computer_get_screen_info",
            "computer_screenshot",
            "computer_move_mouse",
            "computer_click",
            "computer_scroll",
            "computer_type_text",
            "computer_press_key",
            "computer_get_status",
            # Phase 2: Visual verification
            "visual_wait_for_change",
            # Phase 2: Task tracking
            "task_create",
            "task_record_step",
            "task_get_status",
            "task_list_history",
            "task_cancel",
            # Phase 2: Desktop window navigation
            "desktop_list_windows",
            "desktop_focus_window",
            "desktop_get_window_bounds",
            "desktop_set_window_state",
            # Phase 2: Browser automation
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
            # Phase 3: Autonomous Agent & Web UI
            "agent_plan_task",
            "agent_execute_task",
            "web_get_status",
            # Phase 4: Visual Grounding, Macros, Multi-Monitor & Desktop Lifecycle
            "computer_get_monitors",
            "computer_clipboard_get",
            "computer_clipboard_set",
            "desktop_launch_app",
            "desktop_close_app",
            "visual_locate_element",
            "visual_click_element",
            "macro_create",
            "macro_list",
            "macro_execute",
            "macro_delete",
            # Phase 5: Production Automation Scheduler & Audit Exports
            "schedule_create",
            "schedule_list",
            "schedule_delete",
            "schedule_toggle",
            "audit_export_json",
            "audit_export_csv",
        }
        assert expected == tool_names, f"Missing: {expected - tool_names}, Extra: {tool_names - expected}"

    def test_tools_have_descriptions(self, mcp_server):
        srv, _ = mcp_server
        tools = asyncio.run(srv.mcp.list_tools())
        for tool in tools:
            assert tool.description, f"Tool '{tool.name}' has no description"

    def test_tools_have_input_schemas(self, mcp_server):
        srv, _ = mcp_server
        tools = asyncio.run(srv.mcp.list_tools())
        for tool in tools:
            # MCP v2 uses inputSchema or input_schema
            schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None)
            assert schema is not None, f"Tool '{tool.name}' has no input schema"


# ── Tool invocation ───────────────────────────────────────────────────────


class TestToolInvocation:
    def _call(self, srv, name: str, args: dict):
        result = asyncio.run(srv.mcp.call_tool(name, args))
        return result.content

    def test_get_screen_info(self, mcp_server):
        srv, _ = mcp_server
        content = self._call(srv, "computer_get_screen_info", {})
        assert len(content) > 0
        data = json.loads(content[0].text)
        assert data["width"] == 1920
        assert data["height"] == 1080

    def test_get_status(self, mcp_server):
        srv, _ = mcp_server
        content = self._call(srv, "computer_get_status", {})
        data = json.loads(content[0].text)
        assert "runtime_active" in data
        assert "failsafe_enabled" in data
        assert "enabled_tools" in data
        assert data["runtime_active"] is True

    def test_move_mouse_valid(self, mcp_server):
        srv, _ = mcp_server
        content = self._call(srv, "computer_move_mouse", {"x": 100, "y": 200, "duration": 0.1})
        data = json.loads(content[0].text)
        assert data["success"] is True

    def test_move_mouse_invalid_coords(self, mcp_server):
        srv, _ = mcp_server
        # MCP v2 wraps tool exceptions in UnexpectedToolError
        with pytest.raises(Exception, match="out of bounds|Error executing tool"):
            self._call(srv, "computer_move_mouse", {"x": 9999, "y": 9999, "duration": 0.1})

    def test_click_invalid_type(self, mcp_server):
        srv, _ = mcp_server
        with pytest.raises(Exception, match="not allowed|Error executing tool"):
            self._call(srv, "computer_click", {"x": 100, "y": 100, "click_type": "triple"})

    def test_type_text_too_long(self, mcp_server):
        srv, _ = mcp_server
        with pytest.raises(Exception, match="exceeds maximum|Error executing tool"):
            self._call(srv, "computer_type_text", {"text": "a" * 1001})

    def test_press_key_invalid(self, mcp_server):
        srv, _ = mcp_server
        with pytest.raises(Exception, match="not in the allowlist|Error executing tool"):
            self._call(srv, "computer_press_key", {"key": "launch_missiles"})

    def test_press_key_no_args(self, mcp_server):
        srv, _ = mcp_server
        with pytest.raises(Exception, match="Must provide|Error executing tool"):
            self._call(srv, "computer_press_key", {})

    def test_scroll_over_limit(self, mcp_server):
        srv, _ = mcp_server
        with pytest.raises(Exception, match="exceeds maximum|Error executing tool"):
            self._call(srv, "computer_scroll", {"clicks": 100})

    def test_screenshot_returns_image(self, mcp_server):
        srv, _ = mcp_server
        result = self._call(srv, "computer_screenshot", {})
        assert len(result) > 0

    def test_task_tools(self, mcp_server):
        srv, _ = mcp_server
        # 1. task_create
        res = self._call(srv, "task_create", {"description": "Automated workflow test"})
        t_data = json.loads(res[0].text)
        assert t_data["description"] == "Automated workflow test"
        tid = t_data["task_id"]

        # 2. task_record_step
        s_res = self._call(srv, "task_record_step", {
            "task_id": tid,
            "action_name": "computer_get_screen_info",
            "parameters": {},
            "status": "success",
            "result_summary": "Retrieved 1920x1080",
            "visual_verified": True,
        })
        s_data = json.loads(s_res[0].text)
        assert s_data["step_number"] == 1
        assert s_data["visual_verified"] is True

        # 3. task_get_status
        status_res = self._call(srv, "task_get_status", {"task_id": tid})
        status_data = json.loads(status_res[0].text)
        assert status_data["found"] is True
        assert len(status_data["steps"]) == 1

        # 4. task_list_history (returns list of items formatted as content blocks)
        hist_res = self._call(srv, "task_list_history", {"limit": 5})
        hist_items = [json.loads(c.text) for c in hist_res]
        assert isinstance(hist_items, list)
        assert len(hist_items) >= 1

        # 5. task_cancel
        cancel_res = self._call(srv, "task_cancel", {"task_id": tid})
        cancel_data = json.loads(cancel_res[0].text)
        assert cancel_data["cancelled"] is True

    def test_desktop_list_windows(self, mcp_server):
        srv, _ = mcp_server
        res = self._call(srv, "desktop_list_windows", {})
        # Each window (if any) is returned as a TextContent element
        windows = [json.loads(c.text) for c in res]
        assert isinstance(windows, list)

    def test_visual_wait_for_change_tool(self, mcp_server):
        srv, _ = mcp_server
        res = self._call(srv, "visual_wait_for_change", {"timeout": 0.5})
        data = json.loads(res[0].text)
        assert "has_changed" in data
        assert "diff_ratio" in data

    def test_agent_and_web_tools(self, mcp_server):
        srv, _ = mcp_server
        # 1. agent_plan_task
        plan_res = self._call(srv, "agent_plan_task", {"goal": "take a screenshot"})
        plan_data = json.loads(plan_res[0].text)
        assert "steps" in plan_data
        assert len(plan_data["steps"]) >= 1

        # 2. agent_execute_task
        run_res = self._call(srv, "agent_execute_task", {"goal": "check screen info"})
        run_data = json.loads(run_res[0].text)
        assert "status" in run_data
        assert "steps_completed" in run_data

        # 3. web_get_status
        web_res = self._call(srv, "web_get_status", {})
        web_data = json.loads(web_res[0].text)
        assert "dashboard_url" in web_data
        assert "http" in web_data["dashboard_url"]

    def test_phase4_monitors_and_clipboard(self, mcp_server):
        srv, _ = mcp_server
        # 1. computer_get_monitors
        mon_res = self._call(srv, "computer_get_monitors", {})
        mon_data = [json.loads(c.text) for c in mon_res]
        assert len(mon_data) >= 1
        assert "width" in mon_data[0]

        # 2. computer_clipboard_set
        clip_set_res = self._call(srv, "computer_clipboard_set", {"text": "Phase 4 Autopilot Active"})
        clip_set_data = json.loads(clip_set_res[0].text)
        assert clip_set_data["success"] is True

        # 3. computer_clipboard_get
        clip_get_res = self._call(srv, "computer_clipboard_get", {})
        clip_get_data = json.loads(clip_get_res[0].text)
        assert clip_get_data["success"] is True
        assert clip_get_data["content_length"] > 0

    def test_phase4_macro_management(self, mcp_server):
        srv, _ = mcp_server
        # 1. macro_create
        steps = [{"tool": "computer_get_screen_info", "args": {}}]
        create_res = self._call(srv, "macro_create", {
            "name": "Screen Check Macro",
            "description": "Inspects screen dimensions",
            "steps": steps,
        })
        create_data = json.loads(create_res[0].text)
        assert create_data["name"] == "Screen Check Macro"
        macro_id = create_data["id"]

        # 2. macro_list
        list_res = self._call(srv, "macro_list", {})
        list_data = [json.loads(c.text) for c in list_res]
        assert any(m["id"] == macro_id for m in list_data)

        # 3. macro_delete
        del_res = self._call(srv, "macro_delete", {"identifier": macro_id})
        del_data = json.loads(del_res[0].text)
        assert del_data["deleted"] is True


class TestPhase5SchedulerAndAuditTools:
    def _call(self, srv, name, args):
        result = asyncio.run(srv.mcp.call_tool(name, args))
        return result.content

    def test_schedule_lifecycle(self, mcp_server):
        srv, _ = mcp_server
        # 1. schedule_create
        res = self._call(srv, "schedule_create", {
            "name": "Hourly Health Check",
            "interval_seconds": 3600,
            "target": "verify system health",
            "is_macro": False,
        })
        data = json.loads(res[0].text)
        assert data["name"] == "Hourly Health Check"
        sched_id = data["id"]

        # 2. schedule_list
        list_res = self._call(srv, "schedule_list", {})
        list_data = [json.loads(c.text) for c in list_res]
        assert any(s["id"] == sched_id for s in list_data)

        # 3. schedule_toggle
        toggle_res = self._call(srv, "schedule_toggle", {"identifier": sched_id, "enabled": False})
        toggle_data = json.loads(toggle_res[0].text)
        assert toggle_data["enabled"] is False

        # 4. schedule_delete
        del_res = self._call(srv, "schedule_delete", {"identifier": sched_id})
        del_data = json.loads(del_res[0].text)
        assert del_data["deleted"] is True

    def test_audit_exports(self, mcp_server, tmp_path):
        srv, _ = mcp_server
        # Export JSON
        json_file = str(tmp_path / "audit.json")
        res_json = self._call(srv, "audit_export_json", {"output_path": json_file})
        data_json = json.loads(res_json[0].text)
        assert data_json["success"] is True

        # Export CSV
        csv_file = str(tmp_path / "audit.csv")
        res_csv = self._call(srv, "audit_export_csv", {"output_path": csv_file})
        data_csv = json.loads(res_csv[0].text)
        assert data_csv["success"] is True


# ── Policy enforcement ────────────────────────────────────────────────────


class TestToolPolicy:
    def test_disabled_tool_raises(self, mcp_server):
        srv, _ = mcp_server
        original = srv._policy.computer_get_screen_info
        srv._policy.computer_get_screen_info = False
        try:
            with pytest.raises(Exception, match="disabled by policy|Error executing tool"):
                asyncio.run(srv.mcp.call_tool("computer_get_screen_info", {}))
        finally:
            srv._policy.computer_get_screen_info = original


# ── Stdout safety ─────────────────────────────────────────────────────────


class TestStdoutSafety:
    def test_logging_goes_to_stderr(self, capsys):
        """Ensure application logging does not pollute stdout."""
        import logging
        logger = logging.getLogger("local_computer_autopilot")
        logger.info("Test log message for stdout safety check")
        captured = capsys.readouterr()
        assert "Test log message" not in captured.out, (
            "Log message leaked to stdout — this would corrupt MCP protocol"
        )
