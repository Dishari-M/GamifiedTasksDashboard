@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start-devquest.ps1"
if errorlevel 1 (
  echo.
  echo DevQuest failed to start. Check the logs in the backend and frontend folders.
)
pause
