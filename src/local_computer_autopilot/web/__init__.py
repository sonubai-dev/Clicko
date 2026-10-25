"""Clicko Web UI and dashboard module."""

from local_computer_autopilot.web.app import ClickoWebApp, create_app
from local_computer_autopilot.web.server import start_server

__all__ = ["ClickoWebApp", "create_app", "start_server"]
