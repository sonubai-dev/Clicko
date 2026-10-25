"""Tests for Clicko unified CLI runner."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest
from typer.testing import CliRunner

from local_computer_autopilot.cli import app

runner = CliRunner()


def test_cli_version():
    res = runner.invoke(app, ["version"])
    assert res.exit_code == 0
    assert "Clicko" in res.output
    assert "Phase 1" in res.output
    assert "Phase 5" in res.output


def test_cli_status():
    with patch("local_computer_autopilot.computer.controller.ComputerController.get_screen_info") as mock_screen, \
         patch("local_computer_autopilot.computer.controller.ComputerController.get_monitors") as mock_monitors, \
         patch("local_computer_autopilot.computer.controller.ComputerController.get_status") as mock_status:

        mock_screen.return_value = MagicMock(width=1920, height=1080)
        mock_mon = MagicMock(index=0, width=1920, height=1080, x=0, y=0, is_primary=True)
        mock_monitors.return_value = [mock_mon]
        mock_status.return_value = MagicMock(failsafe_enabled=True, action_lock_held=False)

        res = runner.invoke(app, ["status"])
        assert res.exit_code == 0
        assert "System Diagnostics" in res.output
        assert "1920 x 1080" in res.output
        assert "PyAutoGUI Fail-Safe" in res.output


def test_cli_audit_json(tmp_path):
    out_file = str(tmp_path / "cli_audit.json")
    res = runner.invoke(app, ["audit", "--format", "json", "--output", out_file])
    assert res.exit_code == 0
    assert "Audit exported successfully" in res.output
    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert "tasks" in data


def test_cli_audit_csv(tmp_path):
    out_file = str(tmp_path / "cli_audit.csv")
    res = runner.invoke(app, ["audit", "--format", "csv", "--output", out_file])
    assert res.exit_code == 0
    assert "Audit exported successfully" in res.output
    with open(out_file, "r", encoding="utf-8") as f:
        content = f.read()
        assert "task_id,task_description" in content


def test_cli_run_goal():
    with patch("local_computer_autopilot.agent.runner.AutonomousAgent.run_plan") as mock_run:
        mock_res = MagicMock(
            success=True,
            steps_completed=2,
            steps_total=2,
            duration_seconds=1.25,
            error_message="",
        )
        mock_run.return_value = mock_res

        res = runner.invoke(app, ["run", "test quick goal"])
        assert res.exit_code == 0
        assert "Succeeded!" in res.output
