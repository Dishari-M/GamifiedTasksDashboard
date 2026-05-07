# Backend Real-Mode Startup

Use this when a new chat needs to start the backend quickly.

From the repository root:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\start-backend-real.ps1
```

When running this from Codex, launch it outside the sandbox so the detached
server process remains alive after the command finishes.

If port `8000` is already occupied by a stale backend:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\start-backend-real.ps1 -Restart
```

The script reads local secrets and Oracle/OCI values from:

```text
backend\.env.real.local
```

That file is ignored by git through the existing `.env.*` rule. Do not commit
it or paste its contents into logs.

Expected result:

```text
Backend running at http://127.0.0.1:8000 (PID <pid>).
```

Quick verification:

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:8000/" -UseBasicParsing
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/tasks" -UseBasicParsing
```

Logs:

```text
backend\uvicorn-8000-real.out.log
backend\uvicorn-8000-real.err.log
```
