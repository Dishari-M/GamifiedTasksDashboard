# DevQuest Local Start Guide

Use this after extracting or copying the project source code locally. These steps are written so a developer or AI coding assistant can run them from a fresh copy of the project.

## Prerequisites

- Node.js and npm
- Python 3.11+
- PowerShell, Terminal, or equivalent shell

## Before You Start

Open a terminal at the project root. The project root is the folder that contains:

```text
backend/
frontend/
docs/
README.md
```

Do not commit generated folders such as:

```text
frontend/node_modules/
frontend/build/
backend/.venv/
```

## Start Frontend

From the project root:

```powershell
cd frontend
npm install
npm start
```

Frontend URL:

```text
http://localhost:3000
```

To verify the frontend production build:

```powershell
npm run build
```

If port `3000` is already in use, stop the existing frontend process or allow Create React App to choose another port when prompted.

## Start Backend

From the project root:

PowerShell on Windows:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

macOS/Linux:

```bash
cd backend
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Backend URL:

```text
http://127.0.0.1:8000
```

## API Documentation

FastAPI exposes API documentation from the running backend:

```text
Swagger UI:  http://127.0.0.1:8000/docs
ReDoc:       http://127.0.0.1:8000/redoc
OpenAPI JSON: http://127.0.0.1:8000/openapi.json
```

Use Swagger UI when you want to try requests from the browser. Use ReDoc when you want a cleaner read-only API reference for reviewing endpoints, request fields, and response schemas. Both views are generated from the same OpenAPI JSON.

Smoke test:

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:8000/" -UseBasicParsing
```

Expected response:

```json
{"msg":"DevQuest Pro"}
```

If port `8000` is already in use, either stop the existing backend process or start on another port:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8001
```

## Backend Database Environment

DB-backed endpoints require Oracle connection environment variables:

```powershell
$env:DB_USER="DEVQUEST_APP"
$env:DB_PASSWORD="<shared_database_user_password>"
$env:DB_DSN="tasksdb_tp"
$env:DB_WALLET_DIR="$env:USERPROFILE\.oracle\wallet_tasksdb"
$env:DB_WALLET_PASSWORD="<shared_wallet_password>"
$env:DB_POOL_SIZE="10"
```

Set these before starting the backend if you want to use endpoints such as `/tasks` and `/quests`.

macOS/Linux equivalent:

```bash
export DB_USER="DEVQUEST_APP"
export DB_PASSWORD="<shared_database_user_password>"
export DB_DSN="tasksdb_tp"
export DB_WALLET_DIR="$USERPROFILE\\.oracle\\wallet_tasksdb"
export DB_WALLET_PASSWORD="<shared_wallet_password>"
export DB_POOL_SIZE="10"
```

Without these DB variables, the root endpoint `/` can still run, but DB-backed endpoints may fail when they try to connect to Oracle.

Current team ADB default:

```text
DB_USER=DEVQUEST_APP
```

Use `DEVQUEST_APP` for local app runs going forward. The `ADMIN` schema may
contain older or partial table shapes and seed data; do not switch the app back
to `ADMIN` unless the team explicitly confirms the schemas have been synced.

## Backend AI Environment

Local development uses mock AI insight by default:

Set these in the same PowerShell window before starting the backend. These are process environment variables, not values to commit into repo files.

```powershell
$env:DEVQUEST_AI_MODE="mock"
$env:DEVQUEST_DATA_MODE="oracle"
$env:DEVQUEST_AI_PROVIDER="oci_genai"
$env:DB_USER="DEVQUEST_APP"
$env:DB_PASSWORD="<shared_database_user_password>"
$env:DB_DSN="tasksdb_tp"
$env:DB_WALLET_DIR="$env:USERPROFILE\.oracle\wallet_tasksdb"
$env:DB_WALLET_PASSWORD="<shared_wallet_password>"
$env:DB_POOL_SIZE="10"
```

Oracle DB code must use the shared `python-oracledb` pool in `backend/db.py`.
For API request paths, prefer `connection_scope()` so connections are always
returned to the pool:

```python
from db import connection_scope

with connection_scope() as conn:
    cur = conn.cursor()
    cur.execute("SELECT ...")
```

If `get_connection()` is used directly, close it in a `finally` block. Do not
create standalone `oracledb.connect()` connections in API request paths, and do
not keep pooled connections in globals, caches, or long-lived service objects.

All user-scoped APIs must pass the current user from `X-DevQuest-User-Id`
through to Oracle queries. The frontend sends this header from the logged-in
profile, and backend helpers map local ids like `user-1` to
`APP_USERS.USER_ID = 1`. Do not hardcode `USER_ID = 1` in new API code.

For local/demo responsiveness, the backend uses short process-local caches for
read-heavy dashboard data:

| API | Cache key | TTL | Invalidated by |
| --- | --- | --- | --- |
| `GET /api/v1/tasks` | user id, work date, filters | 30 seconds | task create/update/status/complete/working-today writes |
| `GET /api/v1/dashboard/today` | user id, date, data mode | 30 seconds | same task writes and quest generation when it changes working-today rows |

The React app calls `/api/v1/tasks?include_total=false` during initial load so
the task list query can skip the separate `COUNT(*)` round-trip. Keep the
default `include_total=true` behavior for clients/tests that need exact paging
totals.

Later, when OCI Generative AI access is available:

```powershell
$env:DEVQUEST_AI_MODE="real"
$env:DEVQUEST_AI_PROVIDER="oci_genai"
$env:OCI_GENAI_MODEL_ID="your_model_id"
$env:OCI_COMPARTMENT_ID="your_compartment_ocid"
$env:OCI_AUTH_TYPE="config_file"
$env:OCI_CONFIG_PROFILE="DEFAULT"
```

`oci_genai` refers to OCI Generative AI through the Generative AI Service Inference API.

Optional OCI settings:

```powershell
$env:OCI_CONFIG_FILE="C:\Users\your_user\.oci\config"
$env:OCI_GENAI_ENDPOINT="https://inference.generativeai.<region>.oci.oraclecloud.com"
$env:OCI_GENAI_SERVING_MODE="on_demand"
```

Use `OCI_GENAI_SERVING_MODE="dedicated"` only when Oracle provides a dedicated GenAI endpoint OCID. In that case, put the endpoint OCID in `OCI_GENAI_MODEL_ID`.

Restart the backend after changing any `DEVQUEST_*` or `OCI_*` value.

## Common URLs

```text
Frontend: http://localhost:3000
Backend:  http://127.0.0.1:8000
API Docs: http://127.0.0.1:8000/docs
```

## Quick AI Assistant Checklist

If an AI assistant is asked to start the app, it should:

1. Confirm it is in the project root.
2. Start the backend from `backend/` using the virtual environment commands above.
3. Smoke test `http://127.0.0.1:8000/`.
4. Start the frontend from `frontend/` using `npm install` and `npm start`.
5. Open `http://localhost:3000`.
6. Report any missing DB environment variables before testing DB-backed endpoints.
