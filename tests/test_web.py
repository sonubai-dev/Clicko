"""Unit tests for Clicko Web UI and REST API dashboard."""

from __future__ import annotations

import json
from unittest.mock import MagicMock
import pytest
from starlette.testclient import TestClient

from local_computer_autopilot.execution.cancellation import CancellationToken
from local_computer_autopilot.macros.storage import MacroStorage
from local_computer_autopilot.scheduler.storage import ScheduleStorage
from local_computer_autopilot.task import TaskManager, TaskStorage
from local_computer_autopilot.web.app import ClickoWebApp


@pytest.fixture
def mock_controller():
    controller = MagicMock()
    controller.get_screen_info.return_value.model_dump.return_value = {"width": 1920, "height": 1080}
    controller.take_screenshot.return_value = b"\x89PNG_SCREENSHOT_BYTES"
    controller.get_status.return_value.model_dump.return_value = {"runtime_active": True}

    # Phase 4 mocks
    mock_mon = MagicMock()
    mock_mon.model_dump.return_value = {
        "index": 0,
        "device": "\\\\.\\DISPLAY1",
        "is_primary": True,
        "width": 1920,
        "height": 1080,
        "x": 0,
        "y": 0,
        "work_area": {},
    }
    controller.get_monitors.return_value = [mock_mon]

    mock_clip = MagicMock()
    mock_clip.model_dump.return_value = {
        "success": True,
        "content_length": 10,
        "content_preview": "...",
        "message": "OK",
    }
    controller.get_clipboard_text.return_value = mock_clip
    controller.set_clipboard_text.return_value = mock_clip
    return controller


@pytest.fixture
def mock_window_manager():
    wm = MagicMock()
    wm.list_windows.return_value = []
    return wm


@pytest.fixture
def mock_browser_manager():
    bm = MagicMock()
    bm.is_running = False
    return bm


@pytest.fixture
def test_client(mock_controller, mock_window_manager, mock_browser_manager):
    storage = TaskStorage(db_path=":memory:")
    tm = TaskManager(storage=storage)
    token = CancellationToken()
    macro_storage = MacroStorage(db_path=":memory:")
    schedule_storage = ScheduleStorage(db_path=":memory:")

    web_app = ClickoWebApp(
        controller=mock_controller,
        task_manager=tm,
        window_manager=mock_window_manager,
        browser_manager=mock_browser_manager,
        macro_storage=macro_storage,
        schedule_storage=schedule_storage,
        cancellation_token=token,
    )
    return TestClient(web_app.app)


class TestWebDashboard:
    def test_index_dashboard_html(self, test_client):
        resp = test_client.get("/")
        assert resp.status_code == 200
        assert "CLICKO" in resp.text
        assert "EMERGENCY STOP" in resp.text
        assert "Live Desktop Screen" in resp.text

    def test_api_status(self, test_client):
        resp = test_client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "runtime_active" in data
        assert "cancelled" in data
        assert data["cancelled"] is False

    def test_api_screenshot(self, test_client):
        resp = test_client.get("/api/screenshot")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert len(resp.content) > 0

    def test_api_tasks(self, test_client):
        resp = test_client.get("/api/tasks")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_api_emergency_stop(self, test_client):
        resp = test_client.post("/api/emergency-stop")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "Emergency Stop" in data["message"]

        # Status check should now indicate cancelled
        status_resp = test_client.get("/api/status")
        assert status_resp.json()["cancelled"] is True

    def test_api_action_dispatch(self, test_client):
        resp = test_client.post(
            "/api/action",
            json={"action": "computer_get_screen_info", "parameters": {}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["action"] == "computer_get_screen_info"

    def test_api_action_dispatch_invalid(self, test_client):
        resp = test_client.post(
            "/api/action",
            json={"action": "invalid_action_xyz", "parameters": {}},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert data["success"] is False
        assert "error" in data

    def test_api_agent_plan(self, test_client):
        resp = test_client.post(
            "/api/agent/plan",
            json={"goal": "take a screenshot of my screen", "mode": "structured"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "steps" in data
        assert len(data["steps"]) >= 2

    def test_api_agent_run(self, test_client):
        resp = test_client.post(
            "/api/agent/run",
            json={"goal": "take a screenshot of my screen", "mode": "structured"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["status"] == "completed"
        assert data["steps_completed"] >= 2

    def test_api_windows(self, test_client):
        resp = test_client.get("/api/windows")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_cors_rejects_untrusted_origin(self, test_client):
        resp = test_client.options(
            "/api/status",
            headers={
                "Origin": "https://evil.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        # Should not allow evil.com
        assert resp.headers.get("access-control-allow-origin") != "https://evil.com"
        assert resp.headers.get("access-control-allow-origin") != "*"

    def test_xss_protection_in_dashboard(self, test_client):
        resp = test_client.get("/")
        assert resp.status_code == 200
        assert "function escapeHtml" in resp.text
        assert "escapeHtml(t.description)" in resp.text

    def test_api_action_policy_disabled_tool(self, mock_controller, mock_window_manager, mock_browser_manager):
        from local_computer_autopilot.config import AppConfig
        cfg = AppConfig()
        cfg.tool_policy.computer_get_screen_info = False

        storage = TaskStorage(db_path=":memory:")
        tm = TaskManager(storage=storage)
        token = CancellationToken()

        web_app = ClickoWebApp(
            controller=mock_controller,
            task_manager=tm,
            window_manager=mock_window_manager,
            browser_manager=mock_browser_manager,
            cancellation_token=token,
            config=cfg,
        )
        client = TestClient(web_app.app)
        resp = client.post(
            "/api/action",
            json={"action": "computer_get_screen_info", "parameters": {}},
        )
        assert resp.status_code == 400
        assert "disabled by policy" in resp.json()["error"]

    def test_api_monitors(self, test_client):
        resp = test_client.get("/api/monitors")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_api_clipboard(self, test_client):
        set_resp = test_client.post("/api/clipboard", json={"text": "Phase 4 Web Clipboard"})
        assert set_resp.status_code == 200
        assert set_resp.json()["success"] is True

        get_resp = test_client.get("/api/clipboard")
        assert get_resp.status_code == 200
        assert get_resp.json()["success"] is True

    def test_api_macros_lifecycle(self, test_client):
        # 1. Create macro
        create_resp = test_client.post("/api/macros", json={
            "name": "Web Test Macro",
            "description": "Macro created via test",
            "steps": [{"tool": "computer_get_screen_info", "args": {}}],
            "parameters": []
        })
        assert create_resp.status_code == 200
        macro_id = create_resp.json()["id"]

        # 2. List macros
        list_resp = test_client.get("/api/macros")
        assert list_resp.status_code == 200
        assert any(m["id"] == macro_id for m in list_resp.json())

        # 3. Execute macro
        exec_resp = test_client.post(f"/api/macros/{macro_id}/execute", json={"parameters": {}})
        assert exec_resp.status_code == 200, f"Error: {exec_resp.text}"
        assert exec_resp.json()["success"] is True

        # 4. Delete macro
        del_resp = test_client.delete(f"/api/macros/{macro_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["deleted"] is True

    def test_api_approvals_flow(self, test_client):
        # Initial approvals empty
        resp = test_client.get("/api/agent/approvals")
        assert resp.status_code == 200
        assert resp.json() == []

        # Resolving unknown approval returns resolved: false
        res_resp = test_client.post("/api/agent/approve", json={
            "approval_id": "nonexistent",
            "approved": True
        })
        assert res_resp.status_code == 200
        assert res_resp.json()["resolved"] is False

    def test_api_schedules_lifecycle(self, test_client):
        # 1. Create schedule
        create_resp = test_client.post("/api/schedules", json={
            "name": "Web Test Schedule",
            "interval_seconds": 120,
            "target": "verify displays",
            "is_macro": False
        })
        assert create_resp.status_code == 200
        data = create_resp.json()
        assert data["name"] == "Web Test Schedule"
        sched_id = data["id"]

        # 2. List schedules
        list_resp = test_client.get("/api/schedules")
        assert list_resp.status_code == 200
        assert any(s["id"] == sched_id for s in list_resp.json())

        # 3. Toggle schedule
        toggle_resp = test_client.patch(f"/api/schedules/{sched_id}", json={"enabled": False})
        assert toggle_resp.status_code == 200
        assert toggle_resp.json()["enabled"] is False

        # 4. Delete schedule
        del_resp = test_client.delete(f"/api/schedules/{sched_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["deleted"] is True

    def test_api_audit_exports(self, test_client):
        # Export JSON
        json_resp = test_client.get("/api/audit/export/json")
        assert json_resp.status_code == 200
        assert "application/json" in json_resp.headers["content-type"]
        assert "tasks" in json_resp.json()

        # Export CSV
        csv_resp = test_client.get("/api/audit/export/csv")
        assert csv_resp.status_code == 200
        assert "text/csv" in csv_resp.headers["content-type"]
        assert "task_id,task_description" in csv_resp.text

    def test_api_diagnostics(self, test_client):
        resp = test_client.get("/api/diagnostics")
        assert resp.status_code == 200
        data = resp.json()
        assert "screen" in data
        assert "monitors" in data
        assert "status" in data
        assert "schedules_count" in data
        assert "macros_count" in data
