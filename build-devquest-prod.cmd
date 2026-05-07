@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%build-devquest-prod.ps1"
if errorlevel 1 (
  echo.
  echo DevQuest production build failed. Check the frontend build output above.
)
pause
