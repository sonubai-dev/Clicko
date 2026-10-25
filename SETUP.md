# Clicko — Complete Setup Guide

> **Version:** 0.5.0 · **Platform:** Windows 10/11 x64 · **Python:** 3.11+  
> **GitHub:** <https://github.com/sonubai-dev/Clicko>

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Installation](#2-installation)
3. [Environment Variables](#3-environment-variables)
4. [Running Clicko](#4-running-clicko)
5. [MCP Client Integration](#5-mcp-client-integration)
6. [Web Dashboard](#6-web-dashboard)
7. [Safety Guide](#7-safety-guide)
8. [Development](#8-development)
9. [Code Review Findings](#9-code-review-findings)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Prerequisites

| Requirement | Minimum | Notes |
|---|---|---|
| **OS** | Windows 10 (64-bit) | Windows 11 recommended |
| **Python** | 3.11 | 3.12 tested and verified |
| **Git** | Any | For cloning |
| **Node.js / npx** | 18+ | **Optional** — only for MCP Inspector |
| **Microsoft Edge or Chrome** | Pre-installed | Playwright uses these for browser automation |
| **Internet** | Not required | Fully local-first; no cloud, no paid APIs |

> **No administrator privileges required** — the server will warn if run as admin.

---

## 2. Installation

### Step 1 — Clone the repository

```powershell
git clone https://github.com/sonubai-dev/Clicko.git
cd Clicko
```

### Step 2 — Create a virtual environment

```powershell
python -m venv .venv
```

### Step 3 — Install all dependencies (editable mode)

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

> If you see a `Scripts disabled` execution policy error, run once:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### Step 4 — Install Playwright browsers

Clicko uses Playwright for local browser automation (Chromium/Edge):

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
```

> This downloads ~150 MB of browser binaries locally. No cloud account required.

### Step 5 — Verify installation

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

Expected output: **211 passed** in ~25 seconds.

```powershell
.\.venv\Scripts\clicko.exe version
```

Expected output:
```
Clicko v0.5.0
  Phase 1: MCP server + 8 computer control tools
  Phase 2: Visual verification + task tracking + browser automation
  Phase 3: Autonomous agent + Web UI dashboard
  Phase 4: Macros + multi-monitor + visual grounding
  Phase 5: Scheduler + audit exports + production CLI (48 tools)
```

---

## 3. Environment Variables

Create a `.env` file in the project root (or export variables in your shell):

```env
# Logging verbosity: DEBUG | INFO | WARNING | ERROR | CRITICAL
CLICKO_LOG_LEVEL=INFO

# Web dashboard bind host (use 0.0.0.0 to expose on LAN — security risk!)
CLICKO_HOST=127.0.0.1

# Web dashboard HTTP port
CLICKO_PORT=8000

# Rotating log file path (max 10 MB × 5 backups)
CLICKO_LOG_FILE=logs/clicko.log

# Human-in-the-loop approval gating (set to true to require confirmation for every action)
CLICKO_REQUIRE_APPROVAL=false
```

> **Note:** Clicko does NOT load `.env` files automatically. Export variables in your shell session or use your OS environment manager.

### Loading `.env` manually (PowerShell)

```powershell
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]*)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), 'Process')
    }
}
```

### Defaults at a glance

| Variable | Default | Type |
|---|---|---|
| `CLICKO_LOG_LEVEL` | `INFO` | String |
| `CLICKO_HOST` | `127.0.0.1` | String |
| `CLICKO_PORT` | `8000` | Integer |
| `CLICKO_LOG_FILE` | `logs/clicko.log` | Path |
| `CLICKO_REQUIRE_APPROVAL` | `false` | Bool |

---

## 4. Running Clicko

### Option A — Unified CLI (`clicko`)

```powershell
# Show version and phase milestones
.\.venv\Scripts\clicko version

# Show system diagnostics, display info, and fail-safe state
.\.venv\Scripts\clicko status

# Run an autonomous goal from the terminal
.\.venv\Scripts\clicko run "open Edge and search for Python 3.12 release notes"

# Launch the Web UI dashboard
.\.venv\Scripts\clicko web --host 127.0.0.1 --port 8000

# Launch the MCP server over stdio
.\.venv\Scripts\clicko serve

# Export task audit trail
.\.venv\Scripts\clicko audit --format json --output logs/audit.json
.\.venv\Scripts\clicko audit --format csv  --output logs/audit.csv
```

> The `clicko` command is available **only inside the venv**. Activate first with `.\.venv\Scripts\Activate.ps1` to use the bare name.

### Option B — One-click Windows launchers

| Script | Purpose |
|---|---|
| `scripts\start_clicko_web.bat` | Launches the Starlette Web UI dashboard |
| `scripts\start_clicko_mcp.bat` | Launches the MCP stdio server (for Claude Desktop) |

Double-click these `.bat` files from Explorer — they activate the venv automatically.

### Option C — Module directly

```powershell
# MCP stdio server (for direct client integration)
.\.venv\Scripts\python.exe -m local_computer_autopilot.server

# Web dashboard (Uvicorn / Starlette)
.\.venv\Scripts\python.exe -m local_computer_autopilot.web
```

### Option D — MCP Inspector (test tools interactively)

Requires Node.js / npx:

```powershell
npx @modelcontextprotocol/inspector .\.venv\Scripts\python.exe -m local_computer_autopilot.server
```

Open the Inspector UI → **Connect** → **Tools** tab. You should see all 48 tools listed.

---

## 5. MCP Client Integration

### Claude Desktop

Edit `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "clicko": {
      "command": "C:\\Users\\YOUR_USERNAME\\path\\to\\Clicko\\.venv\\Scripts\\python.exe",
      "args": ["-m", "local_computer_autopilot.server"],
      "env": {
        "CLICKO_LOG_LEVEL": "INFO",
        "CLICKO_REQUIRE_APPROVAL": "false"
      }
    }
  }
}
```

> Replace `YOUR_USERNAME` and `path\\to\\Clicko` with your actual paths. Use double backslashes in JSON.

### Any MCP-compatible client

The server speaks **stdio transport** (JSON-RPC 2.0 over stdin/stdout). The client must launch the process and pipe stdin/stdout. Environment variables can be passed via the client config's `env` block.

### Enable human-in-the-loop approval gating

Set `CLICKO_REQUIRE_APPROVAL=true` in the env block. Clicko will pause before every destructive action and wait for an `approval_respond` MCP call with `approved=true`.

---

## 6. Web Dashboard

Start the dashboard:

```powershell
.\.venv\Scripts\clicko web
```

Open **<http://127.0.0.1:8000>** in your browser.

### Dashboard Features

| Feature | URL / Button |
|---|---|
| Live Desktop Viewer | Main page — refreshes every 2s |
| Emergency Stop | Red button — stops all workflows, closes browsers |
| Task Dispatcher | Enter goal → Plan → Execute |
| Audit Log | `/api/tasks` — lists all task history |
| Quick Action Console | Inline tool testing without an MCP client |
| Schedule Manager | `/api/schedules` — view/toggle recurring automations |
| Macro Library | `/api/macros` — manage saved macro workflows |

### REST API endpoints (29 routes)

```
GET  /                     → Dashboard HTML
GET  /api/status           → Runtime diagnostics
GET  /api/screenshot       → Live desktop screenshot (PNG base64)
POST /api/emergency_stop   → Abort all active tasks
POST /api/run_task         → Execute a goal
GET  /api/tasks            → List task history
GET  /api/tasks/{id}       → Task detail + steps
GET  /api/macros           → List macros
POST /api/macros           → Create macro
DELETE /api/macros/{id}    → Delete macro
GET  /api/schedules        → List schedules
POST /api/schedules        → Create schedule
DELETE /api/schedules/{id} → Delete schedule
PATCH /api/schedules/{id}  → Toggle schedule on/off
GET  /api/audit/json       → Export audit as JSON
GET  /api/audit/csv        → Export audit as CSV
...and more
```

---

## 7. Safety Guide

Clicko is designed to be safe by default. Understand the controls before deploying.

### Hardware Fail-safe (PyAutoGUI)

Move the mouse cursor to **any corner of the screen** to trigger an emergency abort. This is handled at the OS level and works even if the Python process is hung.

### Input Limits

| Parameter | Limit | Error if exceeded |
|---|---|---|
| Text length | 1,000 characters | `SafetyError` |
| Scroll clicks | ±20 clicks | Clamped to limit |
| Mouse move duration | 0 – 5 seconds | `SafetyError` |
| Clipboard set | 5,000 characters | `SafetyError` |

### Action Lock

Only one desktop action runs at a time. Concurrent calls block until the active action completes.

### Key Allowlist

`computer_press_key` only accepts keys on a vetted allowlist (arrows, function keys, modifiers, common shortcuts). Arbitrary key strings are rejected.

### Coordinate Validation

All mouse actions verify `(x, y)` are within the current screen bounds before executing.

### Approval Gating

With `CLICKO_REQUIRE_APPROVAL=true`, every action that modifies the system (click, type, scroll, launch app, etc.) pauses and exposes a pending approval object. The operator must send `approval_respond(id, approved=True)` to proceed.

### Logging Safety

Typed text content is **never** written to logs. Only action types and positions are logged.

### STDOUT Protection

STDOUT is reserved exclusively for the MCP protocol (JSON-RPC). All application logging goes to **stderr** and the rotating log file. Never add `print()` calls to server code.

---

## 8. Development

### Running tests

```powershell
# Full suite
.\.venv\Scripts\python.exe -m pytest tests/ -v

# Specific module
.\.venv\Scripts\python.exe -m pytest tests/test_safety.py -v

# With coverage
.\.venv\Scripts\python.exe -m pytest tests/ --cov=src/local_computer_autopilot --cov-report=term-missing
```

### Smoke tests (non-destructive, no mouse movement)

```powershell
# Phase 1 — Basic computer control
.\.venv\Scripts\python.exe scripts\smoke_test.py

# Phase 2 — Visual verification & task tracking
.\.venv\Scripts\python.exe scripts\phase2_smoke_test.py

# Phase 3 — Autonomous agent & web dashboard
.\.venv\Scripts\python.exe scripts\phase3_smoke_test.py

# Phase 4 — Macros, multi-monitor & visual grounding
.\.venv\Scripts\python.exe scripts\phase4_smoke_test.py

# Phase 5 / Production — Full 8-stage end-to-end suite
.\.venv\Scripts\python.exe scripts\production_smoke_test.py
```

### Project layout

```
src/local_computer_autopilot/
├── cli.py               Unified Typer/Rich CLI entry point
├── config.py            Safety limits, tool policy, env vars, logging
├── server.py            FastMCP server + all 48 tool definitions
├── computer/            Phase 1: mouse, keyboard, screen, clipboard
├── vision/              Phase 2 & 4: visual diff + template matching
├── task/                Phase 2: SQLite task lifecycle & audit
├── desktop/             Phase 2 & 4: window manager & app lifecycle
├── browser/             Phase 2: Playwright browser automation
├── execution/           Phase 2: retry engine & cancellation tokens
├── agent/               Phase 3 & 4: planner, runner, approvals
├── macros/              Phase 4: macro storage & parameter replay
├── scheduler/           Phase 5: recurring schedule daemon
├── audit/               Phase 5: JSON & CSV compliance exports
└── web/                 Phase 3-5: Starlette dashboard & REST API
tests/
scripts/
```

### Adding a new tool

1. Define your tool function in the appropriate submodule.
2. Register it in `src/local_computer_autopilot/server.py` using the `@mcp.tool()` decorator.
3. Add the tool name to `ToolPolicy.enabled_tools` in `config.py`.
4. Write a test in `tests/test_mcp_tools.py` asserting the tool is registered.
5. Update the tool count in `README.md` and `SETUP.md`.

### Commit conventions

```
feat: add new tool or feature
fix: bug fix
docs: documentation only
test: add or update tests
refactor: code change without behavior change
chore: build/config changes
```

---

## 9. Code Review Findings

> Analysis performed against the ANTIGRAVITY Production Code Review Standard (P0–P3 severity framework).

### Summary

| Severity | Count | Status |
|---|---|---|
| **P0 — Critical** (data loss / security) | 0 | ✅ None found |
| **P1 — High** (correctness / safety) | 3 | ✅ All resolved |
| **P2 — Medium** (reliability / UX) | 4 | ✅ All resolved |
| **P3 — Low** (polish / maintainability) | 2 | ✅ Noted, accepted |

### P1 Findings (resolved)

| # | Finding | File | Resolution |
|---|---|---|---|
| P1-1 | `UnicodeEncodeError` on Windows cp1252 console from `✔` chars | `cli.py` | Replaced with `[OK]` ASCII-safe markers |
| P1-2 | `audit_export_csv` accessed `t.completed_at` (non-existent field) | `audit/exporter.py` | Changed to `t.updated_at` |
| P1-3 | `ScheduleStorage.create_schedule` raised UNIQUE constraint on duplicate name | `scheduler/storage.py` | Changed `INSERT` to `INSERT OR REPLACE` with `ON CONFLICT` upsert |

### P2 Findings (resolved)

| # | Finding | File | Resolution |
|---|---|---|---|
| P2-1 | `git push` rejected (non-fast-forward) on initial remote setup | N/A | Resolved via `--allow-unrelated-histories` merge strategy |
| P2-2 | HTTP 408 timeout during large initial push (~10K line repo) | N/A | Set `http.postBuffer=524288000` |
| P2-3 | README MCP Inspector step referenced only 8 tools (Phase 1 count) | `README.md` | Updated to 48 tools across all phases |
| P2-4 | Project structure block had duplicate script entries | `README.md` | Cleaned up duplicate lines |

### P3 Findings (accepted)

| # | Finding | Notes |
|---|---|---|
| P3-1 | No `.env` auto-loading (requires manual export or shell script) | By design — avoids third-party dep (`python-dotenv`) |
| P3-2 | Test coverage gaps in scheduler daemon thread exception recovery | Daemon runs in background thread; unit tests mock the scheduler service |

### Security Checklist (Checklist B from review standard)

| Item | Status |
|---|---|
| CORS locked to `localhost` origins only | ✅ |
| No secrets or typed text written to logs | ✅ |
| No admin privilege use or escalation | ✅ |
| Input length limits on all user-supplied strings | ✅ |
| Coordinate bounds checked before every mouse action | ✅ |
| Key allowlist enforced (no arbitrary key injection) | ✅ |
| Screenshot data never leaves local machine | ✅ |
| STDOUT reserved exclusively for MCP protocol | ✅ |

### Reliability Checklist (Checklist G)

| Item | Status |
|---|---|
| SQLite operations wrapped with `threading.Lock` | ✅ |
| Action lock prevents concurrent desktop actions | ✅ |
| Scheduler daemon thread has exception catch-and-continue | ✅ |
| Browser session recovery after crash | ✅ |
| Cancellation tokens propagated through all async paths | ✅ |

---

## 10. Troubleshooting

| Problem | Solution |
|---|---|
| `Scripts disabled` error | `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| `ModuleNotFoundError: local_computer_autopilot` | Run `pip install -e ".[dev]"` inside the venv |
| `playwright._impl._errors.Error: Executable doesn't exist` | Run `.\.venv\Scripts\python.exe -m playwright install chromium` |
| Mouse moves to corner and Clicko aborts | Working as designed — PyAutoGUI fail-safe triggered. Move mouse away from corner and retry. |
| `SafetyError: coordinates out of bounds` | Run `computer_get_screen_info` to get your screen resolution, then use valid coordinates |
| MCP server hangs on startup | The server waits for a MCP client on stdin. Use MCP Inspector or Claude Desktop — don't run interactively |
| Web dashboard not loading | Check `CLICKO_PORT` is not in use: `netstat -ano \| findstr :8000` |
| `UnicodeEncodeError` in terminal output | Set `PYTHONIOENCODING=utf-8` in your shell or use Windows Terminal |
| `git push` rejected | Run `git pull --rebase origin main` first |
| Tests fail with `PermissionError` on SQLite | Delete any leftover `.db` files in `tests/` directory |
| `clicko` command not found | Make sure you're in the venv: `.\.venv\Scripts\Activate.ps1` |

---

*Generated by Antigravity code analysis · Clicko v0.5.0 · Windows local-first*
