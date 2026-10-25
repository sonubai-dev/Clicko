@echo off
rem Clicko MCP Server stdio launcher for Claude Desktop / MCP Clients
cd /d "%~dp0\.."

if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe -m local_computer_autopilot.cli serve
) else (
    clicko serve
)
