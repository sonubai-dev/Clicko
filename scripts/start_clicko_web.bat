@echo off
title Clicko Web Dashboard
cd /d "%~dp0\.."

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

echo =======================================================
echo   Clicko - Enterprise Local Windows Computer Autopilot
echo   Starting Web Dashboard at http://127.0.0.1:8000
echo =======================================================

clicko web --host 127.0.0.1 --port 8000
pause
