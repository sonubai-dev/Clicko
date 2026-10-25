# LocalComputerAutopilot (Clicko)

A local-first Windows AI Computer Autopilot — MCP server for safe computer control, browser automation, visual grounding, scheduled workflows, and enterprise compliance.

> **Phase 1**: MCP server with 8 computer-control tools, hardware fail-safe, and strict safety validation.
> **Phase 2**: Visual verification, persistent task tracking (SQLite), Windows desktop navigation, and local browser automation (Playwright/Edge).
> **Phase 3**: Interactive Web UI Dashboard, Emergency Stop, Autonomous Workflow Planning, and Local AI Reasoning.
> **Phase 4**: Visual template grounding, multi-monitor display management, system clipboard, Windows desktop application lifecycle, automation macro workflows, and human-in-the-loop operator safeguards.
> **Phase 5**: Production automation scheduler, JSON/CSV compliance audit trail exports, unified CLI runner (`clicko`), Windows production launchers, rotating file logging, and 48 MCP tools.

## Prerequisites

- **Windows 10/11** (64-bit)
- **Python 3.11+** installed and on PATH
- Microsoft Edge or Google Chrome (pre-installed on Windows)
- No paid APIs, cloud services, or external backend required

## Quick Start (PowerShell)

### 1. Clone / navigate to the project

```powershell
cd c:\Users\sonu\Documents\antigravity\busy-babbage
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
```

### 3. Activate the virtual environment

```powershell
# If script execution is restricted, use this instead:
.\.venv\Scripts\python.exe -m pip install --upgrade pip

# Or enable scripts first (run once as Administrator):
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 4. Install dependencies

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

### 5. Run tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

### 6. Launch the MCP server

```powershell
.\.venv\Scripts\python.exe -m local_computer_autopilot.server
```

The server runs on **stdio transport** — it reads JSON-RPC from stdin and writes to stdout. This is how MCP clients communicate with it.

### 7. Launch the Clicko Web UI Dashboard

```powershell
.\.venv\Scripts\python.exe -m local_computer_autopilot.web
```

Open **`http://127.0.0.1:8000`** in your browser.
Features include:
- **Live Desktop Screen Viewer**: Real-time snapshot monitor.
- **Big Red Emergency Stop**: Single-click abort stopping active workflows and closing browsers.
- **Autonomous Task Dispatcher**: Enter goals in natural language to plan and execute tasks.
- **SQLite Task Audit Log**: Review task history, duration, and step-by-step outcomes.
- **Quick Action Console**: Direct interactive testing of tools without external clients.

### 8. Test with MCP Inspector

```powershell
# Install MCP Inspector (requires Node.js/npx)
npx @modelcontextprotocol/inspector .\.venv\Scripts\python.exe -m local_computer_autopilot.server
```

In the Inspector UI:
1. Click **Connect**
2. Go to the **Tools** tab
3. You should see all 8 `computer_*` tools listed
4. Click a tool (e.g., `computer_get_screen_info`) and click **Run**
5. You should see a structured JSON response with screen dimensions

### 9. Connect a compatible MCP client

Add this to your MCP client configuration (e.g., Claude Desktop `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "local-computer-autopilot": {
      "command": "c:\\Users\\sonu\\Documents\\antigravity\\busy-babbage\\.venv\\Scripts\\python.exe",
      "args": ["-m", "local_computer_autopilot.server"]
    }
  }
}
```

> **Note**: Adjust the Python path to your actual `.venv` location. The server communicates over stdio — the MCP client launches and manages the process.

### 10. Stop the server

The server exits when the MCP client disconnects (stdin closes), or press **Ctrl+C**.

## MCP Tools Reference

### Phase 1: Computer Control

| Tool | Description | Side Effects |
|------|-------------|-------------|
| `computer_get_screen_info` | Returns screen width and height in pixels | None (read-only) |
| `computer_screenshot` | Captures and returns a screenshot as PNG | None (in-memory, not saved) |
| `computer_move_mouse` | Moves mouse cursor to (x, y) with bounded duration | Moves cursor |
| `computer_click` | Clicks at (x, y) with allowlisted click type (`left`, `right`, `middle`, `double`) | Performs click |
| `computer_scroll` | Scrolls vertically or horizontally (bounded ±20 clicks) | Performs scroll |
| `computer_type_text` | Types text via keyboard (max 1000 chars, content unlogged) | Types keys |
| `computer_press_key` | Presses allowlisted key or key combination (e.g. `['ctrl', 's']`) | Presses keys |
| `computer_get_status` | Returns runtime status, fail-safe state, and enabled tools | None (read-only) |

### Phase 2: Visual Verification

| Tool | Description | Side Effects |
|------|-------------|-------------|
| `visual_wait_for_change` | Polls until a visual change occurs on screen or within a bounding box | None (read-only) |

### Phase 2: Task Tracking & Auditing (SQLite)

| Tool | Description | Side Effects |
|------|-------------|-------------|
| `task_create` | Creates a new tracked workflow session | Writes task to local SQLite DB |
| `task_record_step` | Records an executed action step with status and verification | Writes step to local SQLite DB |
| `task_get_status` | Retrieves full execution history and step status for a task | Reads from local SQLite DB |
| `task_list_history` | Lists recent task executions and outcomes | Reads from local SQLite DB |
| `task_cancel` | Marks task cancelled and triggers cooperative runtime cancellation | Updates DB & sets cancellation token |

### Phase 2: Windows Desktop Navigation

| Tool | Description | Side Effects |
|------|-------------|-------------|
| `desktop_list_windows` | Lists visible top-level application windows with coordinates and titles | None (read-only) |
| `desktop_focus_window` | Brings target application window to the foreground | Focuses window |
| `desktop_get_window_bounds` | Retrieves current screen rectangle (`x`, `y`, `width`, `height`) of a window | None (read-only) |
| `desktop_set_window_state` | Sets window state (`maximize`, `minimize`, `restore`, `normal`) | Changes window state |

### Phase 2: Local Browser Automation (Playwright / Edge)

| Tool | Description | Side Effects |
|------|-------------|-------------|
| `browser_open` | Launches or navigates local browser to URL (Edge/Chrome) | Launches/navigates browser |
| `browser_new_tab` | Opens a new browser tab and optionally navigates to URL | Opens new tab |
| `browser_list_tabs` | Lists all open tabs in current session | None (read-only) |
| `browser_switch_tab` | Switches active focus to specified tab index | Switches tab focus |
| `browser_close_tab` | Closes specified tab or active tab | Closes tab |
| `browser_click` | Clicks web page element matching CSS/XPath selector | Interacts with DOM element |
| `browser_type` | Types into input element (text content masked from logs) | Inputs text |
| `browser_get_content` | Extracts text from page body or specific element selector | None (read-only) |
| `browser_screenshot` | Captures active browser viewport as PNG image | Returns in-memory image |
| `browser_close` | Closes browser session completely | Closes browser process |

### Phase 3: Autonomous Agent & Web UI

| Tool | Description | Side Effects |
|------|-------------|-------------|
| `agent_plan_task` | Generates and previews a multi-step execution plan for a goal without executing | None (read-only) |
| `agent_execute_task` | Plans and autonomously runs a task with visual verification and SQLite audit | Executes planned computer/browser actions |
| `web_get_status` | Returns the Clicko Web UI dashboard status, URL (`http://127.0.0.1:8000`), and quick-start instructions | None (read-only) |

### Phase 4: Visual Grounding, Macros, Multi-Monitor & Desktop Lifecycle

| Tool | Description | Side Effects |
|------|-------------|-------------|
| `computer_get_monitors` | Enumerates all connected physical/virtual displays with bounds, resolution, and work areas | None (read-only) |
| `computer_clipboard_get` | Safely inspects current textual contents on the Windows system clipboard | None (read-only) |
| `computer_clipboard_set` | Safely copies text onto the Windows system clipboard (max 5000 chars) | Modifies system clipboard |
| `desktop_launch_app` | Launches a Windows desktop application safely without shell execution | Spawns application process |
| `desktop_close_app` | Closes an application window gracefully via `WM_CLOSE` | Requests window close |
| `visual_locate_element` | Locates an icon, button, or template image on screen using Pillow template matching | None (read-only) |
| `visual_click_element` | Locates a template image on screen and performs a click at its center coordinates | Performs mouse click |
| `macro_create` | Creates and saves a persistent, reusable automation macro workflow with parameters | Writes macro to SQLite |
| `macro_list` | Lists all saved automation macros and their step sequences | Reads macros from SQLite |
| `macro_execute` | Replays a saved macro with optional parameter substitution and SQLite auditing | Executes planned macro steps |
| `macro_delete` | Removes a saved macro from SQLite storage | Deletes macro from SQLite |

### Phase 5: Production Automation Scheduler & Audit Exports

| Tool | Description | Side Effects |
|------|-------------|-------------|
| `schedule_create` | Creates an automated recurring workflow schedule (minimum 5s interval) | Writes schedule to SQLite |
| `schedule_list` | Lists all registered recurring automation schedules | Reads schedules from SQLite |
| `schedule_delete` | Deletes a recurring automation schedule by ID or name | Deletes schedule from SQLite |
| `schedule_toggle` | Enables or pauses a recurring automation schedule | Updates schedule in SQLite |
| `audit_export_json` | Exports task history and execution step audits to JSON format | Generates JSON or writes file |
| `audit_export_csv` | Exports flattened task steps to CSV for spreadsheet compliance audits | Generates CSV or writes file |

## Clicko Unified CLI Reference

Clicko features a comprehensive CLI powered by Typer and Rich:

```powershell
# Display version and phase milestones
clicko version

# Inspect system diagnostics, display resolutions, and fail-safe state
clicko status

# Execute an autonomous workflow goal directly from the terminal
clicko run "open edge and search for python"

# Launch the interactive Starlette Web Dashboard
clicko web --host 127.0.0.1 --port 8000

# Start the FastMCP server over stdio transport
clicko serve

# Export task compliance audit trail
clicko audit --format json --output logs/audit.json
clicko audit --format csv --output logs/audit.csv
```

## Production Windows Launchers

For enterprise and one-click desktop convenience, Clicko provides batch launchers:
- **`scripts\start_clicko_web.bat`**: One-click launcher for the Starlette Web UI dashboard.
- **`scripts\start_clicko_mcp.bat`**: One-click launcher for MCP stdio clients (Claude Desktop).
- **`scripts\production_smoke_test.py`**: Full 8-stage end-to-end production smoke test.

## Safety Controls

- **PyAutoGUI fail-safe**: Move mouse to any screen corner to abort (enabled by default)
- **Coordinate validation**: All coordinates checked against screen bounds
- **Input limits**: Text max 1000 chars, scroll max ±20 clicks, duration max 5s
- **Key allowlist**: Only documented, safe keys are accepted
- **Concurrency lock**: Only one desktop action at a time
- **No admin privileges**: Server refuses to describe itself as safe under admin
- **No external data**: Screenshots and keystrokes never leave your machine
- **Logging safety**: Typed text content is never written to logs

## Manual Smoke Tests

### Phase 1: Basic Computer Control Smoke Test
```powershell
.\.venv\Scripts\python.exe scripts\smoke_test.py
```
This script reports screen info and safely moves the mouse cursor slightly after asking for explicit confirmation.

### Phase 2: Visual Verification & Automation Workflows Smoke Test
```powershell
.\.venv\Scripts\python.exe scripts\phase2_smoke_test.py
```
This non-destructive script verifies:
1. Visual verification & pixel difference detection
2. Task tracking & SQLite audit trail
3. Windows desktop application discovery
4. Reliable execution (retries, timeouts, cancellation tokens)
5. Local browser automation readiness (Playwright / Edge)

### Phase 3: Autonomous Agent, Web Dashboard & Local Reasoning Smoke Test
```powershell
.\.venv\Scripts\python.exe scripts\phase3_smoke_test.py
```
This non-destructive script verifies:
1. Autonomous workflow planning (deterministic rules & local LLM check)
2. Autonomous agent execution loop with step auditing and visual verification
3. Clicko Web UI Dashboard and REST API endpoints (Starlette / Uvicorn)
4. Emergency Stop abort trigger
5. Complete MCP tool inventory check

### Phase 4: Visual Grounding, Macros, Displays & App Control Smoke Test
```powershell
.\.venv\Scripts\python.exe scripts\phase4_smoke_test.py
```
This non-destructive script verifies:
1. Multi-monitor display detection & screen bounds
2. Safe system clipboard read and write
3. Visual template needle-in-haystack locator
4. Reusable macro workflow storage, execution & deletion
5. Windows application lifecycle
6. Complete 42 MCP tool inventory check

### Phase 5 & Final Production: End-to-End Enterprise Smoke Test
```powershell
.\.venv\Scripts\python.exe scripts\production_smoke_test.py
```
This non-destructive comprehensive suite verifies:
1. Controller, screen info, and hardware fail-safe active
2. Multi-monitor enumeration and system clipboard read/write
3. SQLite task lifecycle, step recording, and audit trails
4. Reusable macro creation, execution, and storage
5. Automated recurring workflow scheduler service & storage
6. Compliance audit trail exports in both JSON and CSV
7. Starlette Web UI with 29 production routes and diagnostics
8. Complete 48 FastMCP tool inventory check (100% passing)

## Project Structure

```
src/local_computer_autopilot/
├── __init__.py          # Package version (0.5.0)
├── cli.py               # Unified Typer/Rich CLI ('clicko')
├── config.py            # Safety limits, tool policy, rotating file logging
├── server.py            # MCPServer + 48 tool definitions
├── computer/            # Phase 1: Controller, safety checks, models
│   ├── controller.py    # Screen info, monitors, clipboard, mouse/keyboard
│   ├── safety.py        # Validation boundaries and action lock
│   └── models.py
├── vision/              # Phase 2 & 4: Visual verification & template grounding
│   ├── verifier.py      # Diff detection, ROI wait, template locator
│   └── models.py
├── task/                # Phase 2: SQLite task tracking & audit
│   ├── storage.py
│   ├── manager.py
│   └── models.py
├── desktop/             # Phase 2 & 4: Windows desktop & application navigation
│   ├── window_manager.py # Window focus, state, launch_app, close_app
│   └── models.py
├── browser/             # Phase 2: Local browser automation (Playwright/Edge)
│   ├── browser_manager.py
│   └── models.py
├── execution/           # Phase 2: Retries, timeouts, cancellation tokens
│   ├── retry.py
│   └── cancellation.py
├── agent/               # Phase 3 & 4: Autonomous workflow planning & approvals
│   ├── models.py
│   ├── planner.py
│   └── runner.py        # AutonomousAgent execution loop & approval safeguards
├── macros/              # Phase 4: Automation Macro workflow engine
│   ├── models.py        # MacroDefinition, MacroExecutionResult
│   ├── storage.py       # SQLite macro storage
│   └── runner.py        # Parameter interpolation & replay runner
├── scheduler/           # Phase 5: Production recurring workflow scheduler
│   ├── models.py        # ScheduleDefinition, ScheduleExecutionResult
│   ├── storage.py       # SQLite schedule storage (UPSERT, toggle, record_run)
│   └── service.py       # Background scheduler daemon thread
├── audit/               # Phase 5: Enterprise compliance audit exports
│   └── exporter.py      # export_audit_json & export_audit_csv
└── web/                 # Phase 3, 4 & 5: Starlette Web UI dashboard & REST API
    ├── app.py           # ClickoWebApp, dashboard HTML, REST API routes
    └── server.py        # Uvicorn server launcher
tests/
├── conftest.py                # Fixtures & mocks
├── test_safety.py             # Safety validation tests
├── test_controller.py         # Controller tests (mocked)
├── test_monitors_clipboard.py # Multi-monitor and clipboard tests
├── test_mcp_tools.py          # MCP tool registration & invocation tests (48 tools)
├── test_vision.py             # Visual verification & template locator tests
├── test_task_manager.py       # SQLite task tracking tests
├── test_desktop.py            # Desktop window management & app lifecycle tests
├── test_browser.py            # Browser automation tests
├── test_execution.py          # Retries and cancellation token tests
├── test_agent.py              # Autonomous agent & planner tests
├── test_macros.py             # Macro storage, runner, parameter interpolation tests
├── test_approval.py           # Human-in-the-loop approval safeguard tests
├── test_web.py                # Starlette Web UI & REST API tests
├── test_scheduler.py          # Phase 5 recurring scheduler tests
├── test_audit.py              # Phase 5 JSON & CSV compliance export tests
└── test_cli.py                # Phase 5 Clicko unified CLI runner tests
scripts/
├── start_clicko_web.bat       # One-click Windows Web UI launcher
├── start_clicko_mcp.bat       # One-click Windows MCP server launcher
├── production_smoke_test.py   # Final 8-stage production verification suite
├── smoke_test.py              # Phase 1: Manual non-destructive smoke test
├── phase2_smoke_test.py       # Phase 2: Non-destructive workflow verification
├── phase3_smoke_test.py       # Phase 3: Web UI and autonomous workflow verification
└── phase4_smoke_test.py       # Phase 4: Grounding, macros, displays & app control
├── phase2_smoke_test.py       # Phase 2: Non-destructive workflow verification
├── phase3_smoke_test.py       # Phase 3: Web UI and autonomous workflow verification
└── phase4_smoke_test.py       # Phase 4: Grounding, macros, displays & app control
```

## Known Limitations

- **Desktop automation is not 100% reliable**: Screen elements may move, pop-ups may appear, timing varies. Do not assume an action succeeded just because no error was raised.
- **Local LLM optionality**: Autonomous planning works out-of-the-box using built-in deterministic workflow rules; running Ollama locally adds open-source LLM reasoning with 0 mandatory paid APIs.
- **`typewrite` limitation**: PyAutoGUI's `typewrite` only supports ASCII. Non-ASCII text uses `write()` which may behave differently across keyboard layouts.
- **MCP client compatibility**: Tested with MCP Inspector. Other clients should work via the standard stdio transport but are not individually verified.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Scripts disabled` error | Run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| `ModuleNotFoundError` | Make sure you installed with `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"` |
| Mouse moves to corner and fails | That's the PyAutoGUI fail-safe — it's working correctly! |
| `SafetyError: coordinates out of bounds` | Check your screen resolution with `computer_get_screen_info` first |
| Server hangs on startup | The server waits for MCP protocol messages on stdin — use MCP Inspector or a client |

## License

MIT
