"""Phase 3 Smoke Test — Verifies Autonomous Workflow Planning, Execution, and Web UI.

Demonstrates:
1. Autonomous Workflow Planning (rule-based and local LLM check)
2. Autonomous Agent Execution Loop with step audit and visual verification
3. Clicko Web UI Dashboard and REST API endpoints (Starlette / Uvicorn)
4. Emergency Stop abort trigger
5. Full MCP tool inventory check (31 tools)

Run with:
    .\\.venv\\Scripts\\python.exe scripts\\phase3_smoke_test.py
"""

from __future__ import annotations

import asyncio
from starlette.testclient import TestClient

from local_computer_autopilot.agent import AgentMode, AutonomousAgent, WorkflowPlanner
from local_computer_autopilot.execution.cancellation import CancellationToken
from local_computer_autopilot.server import mcp
from local_computer_autopilot.task import TaskManager, TaskStorage
from local_computer_autopilot.web.app import ClickoWebApp


def test_workflow_planner() -> None:
    print("\n--- 1. Testing Autonomous Workflow Planner ---")
    planner = WorkflowPlanner()

    # Plan a browser search task
    plan1 = planner.plan("open browser and search for python documentation")
    print(f"  Goal: '{plan1.goal}'")
    print(f"  Planner Mode: {plan1.mode_used.value}")
    print(f"  Steps Planned: {len(plan1.steps)}")
    for s in plan1.steps:
        print(f"    - Step {s.step_number}: {s.action_name} ({s.description})")
    assert len(plan1.steps) >= 3, "Expected at least 3 planned steps for browser search"

    # Plan a screen inspection task
    plan2 = planner.plan("take a screenshot of my desktop")
    print(f"  Goal: '{plan2.goal}' -> {len(plan2.steps)} steps planned")
    assert len(plan2.steps) >= 2, "Expected at least 2 planned steps for screenshot"
    print("  [PASS] Autonomous Workflow Planner functioning as expected.")


def test_autonomous_execution_loop() -> None:
    print("\n--- 2. Testing Autonomous Execution Loop & SQLite Audit ---")
    storage = TaskStorage(db_path=":memory:")
    tm = TaskManager(storage=storage)
    token = CancellationToken()
    planner = WorkflowPlanner()
    agent = AutonomousAgent(task_manager=tm, cancellation_token=token)

    plan = planner.plan("inspect screen and check open windows")
    print(f"  Executing plan with {len(plan.steps)} steps...")
    result = agent.run_plan(plan)

    print(f"  Execution result: status={result.status}, success={result.success}")
    print(f"  Steps completed: {result.steps_completed}/{result.steps_total} ({result.duration_seconds}s)")
    for d in result.step_details:
        print(f"    * Step {d.step_number} ({d.action_name}): {d.status} -> {d.result_summary}")

    audit = tm.get_task_status(result.task_id)
    print(f"  SQLite Audit record: {len(audit['steps'])} steps persisted.")
    assert result.success is True, "Expected autonomous run to succeed"
    print("  [PASS] Autonomous execution loop functioning as expected.")


def test_web_ui_and_emergency_stop() -> None:
    print("\n--- 3. Testing Web Dashboard & Emergency Stop (Starlette) ---")
    storage = TaskStorage(db_path=":memory:")
    tm = TaskManager(storage=storage)
    token = CancellationToken()
    web_app = ClickoWebApp(task_manager=tm, cancellation_token=token)
    client = TestClient(web_app.app)

    # 1. Test HTML Dashboard
    resp_index = client.get("/")
    assert resp_index.status_code == 200
    assert "CLICKO" in resp_index.text
    print("  [PASS] Web Dashboard HTML served successfully.")

    # 2. Test Status Endpoint
    resp_status = client.get("/api/status")
    assert resp_status.status_code == 200
    status_data = resp_status.json()
    print(f"  Runtime Status: active={status_data.get('runtime_active')}, cancelled={status_data.get('cancelled')}")

    # 3. Test Action Dispatcher
    resp_action = client.post("/api/action", json={"action": "computer_get_screen_info", "parameters": {}})
    assert resp_action.status_code == 200
    print(f"  Web Action Dispatcher: {resp_action.json()['result']}")

    # 4. Test Emergency Stop
    print("  Triggering Emergency Stop via Web API...")
    resp_stop = client.post("/api/emergency-stop")
    assert resp_stop.status_code == 200
    stop_data = resp_stop.json()
    print(f"  Emergency Stop: {stop_data['message']}")
    assert token.is_cancelled is True, "Expected cancellation token to be set"
    print("  [PASS] Emergency Stop verified and functional.")


def test_mcp_tool_inventory() -> None:
    print("\n--- 4. Testing Complete MCP Tool Inventory ---")
    tools = asyncio.run(mcp.list_tools())
    tool_names = [t.name for t in tools]
    print(f"  Total Registered MCP Tools: {len(tool_names)}")
    phase3_tools = ["agent_plan_task", "agent_execute_task", "web_get_status"]
    for pt in phase3_tools:
        assert pt in tool_names, f"Missing Phase 3 tool: {pt}"
        print(f"    - {pt} [REGISTERED]")
    assert len(tool_names) >= 31, f"Expected at least 31 tools, found {len(tool_names)}"
    print(f"  [PASS] {len(tool_names)} tools registered across Phases 1, 2, 3, and 4.")


def main() -> None:
    print("=" * 65)
    print(" Clicko Phase 3 Smoke Test: Web UI, Agent Loop & Local Reasoning")
    print("=" * 65)

    test_workflow_planner()
    test_autonomous_execution_loop()
    test_web_ui_and_emergency_stop()
    test_mcp_tool_inventory()

    print("\n" + "=" * 65)
    print(" ALL PHASE 3 SMOKE TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 65)


if __name__ == "__main__":
    main()
