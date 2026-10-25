"""Unit tests for Phase 5 compliance audit exports (JSON & CSV)."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from local_computer_autopilot.audit.exporter import export_audit_csv, export_audit_json
from local_computer_autopilot.task.manager import TaskManager
from local_computer_autopilot.task.models import StepStatus
from local_computer_autopilot.task.storage import TaskStorage


@pytest.fixture
def populated_storage():
    storage = TaskStorage(db_path=":memory:")
    tm = TaskManager(storage=storage)

    # Task 1: Completed with 2 steps
    t1 = tm.create_task("Open Edge and search documentation")
    tm.record_step(
        task_id=t1.task_id,
        action_name="browser_open",
        parameters={"url": "https://bing.com"},
        status=StepStatus.SUCCESS,
        result_summary="Page loaded",
        visual_verified=True,
    )
    tm.record_step(
        task_id=t1.task_id,
        action_name="browser_type",
        parameters={"selector": "input", "text": "Clicko Python"},
        status=StepStatus.SUCCESS,
        result_summary="Typed query",
        visual_verified=False,
    )
    tm.complete_task(t1.task_id)

    # Task 2: Failed with 1 step
    t2 = tm.create_task("Close unauthorized system window")
    tm.record_step(
        task_id=t2.task_id,
        action_name="desktop_close_app",
        parameters={"query": "nonexistent.exe"},
        status=StepStatus.FAILED,
        error_message="Window not found",
    )
    tm.fail_task(t2.task_id, error_message="Window not found")

    return storage, t1.task_id, t2.task_id


def test_export_audit_json_all(populated_storage, tmp_path):
    storage, t1_id, t2_id = populated_storage

    # In-memory string export
    json_str = export_audit_json(storage)
    data = json.loads(json_str)
    assert "tasks" in data
    assert len(data["tasks"]) == 2

    # Verify task details and steps
    task_ids = {t["task"]["task_id"] for t in data["tasks"]}
    assert t1_id in task_ids
    assert t2_id in task_ids

    # File export
    out_file = str(tmp_path / "all_audit.json")
    res_str = export_audit_json(storage, output_path=out_file)
    assert Path(out_file).exists()
    assert json.loads(Path(out_file).read_text(encoding="utf-8")) == data


def test_export_audit_json_single_task(populated_storage):
    storage, t1_id, _ = populated_storage

    json_str = export_audit_json(storage, task_id=t1_id)
    data = json.loads(json_str)
    assert "task" in data
    assert "steps" in data
    assert data["task"]["task_id"] == t1_id
    assert len(data["steps"]) == 2
    assert data["steps"][0]["action_name"] == "browser_open"


def test_export_audit_csv(populated_storage, tmp_path):
    storage, t1_id, t2_id = populated_storage

    # In-memory string export
    csv_str = export_audit_csv(storage)
    assert "task_id,task_description,task_status" in csv_str
    assert "Open Edge and search documentation" in csv_str
    assert "browser_open" in csv_str
    assert "YES" in csv_str  # visual_verified=True

    # File export
    out_file = str(tmp_path / "audit.csv")
    res_str = export_audit_csv(storage, output_path=out_file)
    assert Path(out_file).exists()
    assert Path(out_file).read_text(encoding="utf-8") == csv_str
