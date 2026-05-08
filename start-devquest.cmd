@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
@REM if not defined DB_POOL_SIZE set "DB_POOL_SIZE=2"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start-devquest.ps1"
if errorlevel 1 (
  echo.
  echo Gamified Tasks Dashboard failed to start. Check the logs in the backend and frontend folders.
)
pause
