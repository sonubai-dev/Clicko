"""Web server entrypoint for Clicko Dashboard."""

from __future__ import annotations

import logging
import sys
import uvicorn

from local_computer_autopilot.web.app import create_app

logger = logging.getLogger("local_computer_autopilot.web.server")


def start_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Launch the Clicko Web UI dashboard server using Uvicorn."""
    print("=" * 65)
    print(" 🚀 CLICKO AUTOPILOT WEB DASHBOARD")
    print(f" URL: http://{host}:{port}")
    print(" Features: Live Screen Viewer, Task History, Emergency Stop,")
    print("           Autonomous Planner, and Action Dispatcher")
    print(" Press Ctrl+C to stop.")
    print("=" * 65)

    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level="info")


def main() -> None:
    host = "127.0.0.1"
    port = 8000
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    start_server(host=host, port=port)


if __name__ == "__main__":
    main()
