@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%stop-devquest.ps1"
if errorlevel 1 (
  echo.
  echo DevQuest stop failed.
)
pause
