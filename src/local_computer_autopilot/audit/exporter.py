"""Audit trail export for compliance and task history (JSON and CSV)."""

from __future__ import annotations

import csv
import io
import json
import logging
from pathlib import Path
from typing import Any

from local_computer_autopilot.task.storage import TaskStorage

logger = logging.getLogger("local_computer_autopilot.audit")


def export_audit_json(
    storage: TaskStorage,
    task_id: str | None = None,
    output_path: str | None = None,
) -> str:
    """Export task history and execution step audits to formatted JSON."""
    if task_id:
        task = storage.get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found")
        steps = storage.get_steps(task_id)
        data = {
            "task": task.model_dump(),
            "steps": [s.model_dump() for s in steps],
        }
    else:
        recent_tasks = storage.list_tasks(limit=100)
        all_records = []
        for t in recent_tasks:
            steps = storage.get_steps(t.task_id)
            all_records.append({
                "task": t.model_dump(),
                "steps": [s.model_dump() for s in steps],
            })
        data = {"tasks": all_records}

    json_str = json.dumps(data, indent=2)

    if output_path:
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json_str, encoding="utf-8")
        logger.info("Exported JSON audit log to %s", output_path)

    return json_str


def export_audit_csv(
    storage: TaskStorage,
    output_path: str | None = None,
) -> str:
    """Export flattened task steps to CSV for spreadsheet audit inspection."""
    tasks = storage.list_tasks(limit=200)

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow([
        "task_id",
        "task_description",
        "task_status",
        "task_created_at",
        "task_updated_at",
        "step_number",
        "action_name",
        "parameters",
        "step_status",
        "result_summary",
        "visual_verified",
        "error_message",
    ])

    for t in tasks:
        steps = storage.get_steps(t.task_id)
        if not steps:
            writer.writerow([
                t.task_id,
                t.description,
                t.status.value,
                t.created_at,
                t.updated_at,
                "",
                "",
                "",
                "",
                "",
                "",
                t.error_message or "",
            ])
        else:
            for s in steps:
                writer.writerow([
                    t.task_id,
                    t.description,
                    t.status.value,
                    t.created_at,
                    t.updated_at,
                    s.step_number,
                    s.action_name,
                    json.dumps(s.parameters),
                    s.status.value,
                    s.result_summary or "",
                    "YES" if s.visual_verified else "NO",
                    s.error_message or "",
                ])

    csv_str = output.getvalue()

    if output_path:
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(csv_str, encoding="utf-8", newline="")
        logger.info("Exported CSV audit log to %s", output_path)

    return csv_str
