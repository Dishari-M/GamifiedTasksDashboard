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
$env:DB_USER="your_db_user"
$env:DB_PASSWORD="your_db_password"
$env:DB_DSN="your_db_dsn"
```

Set these before starting the backend if you want to use endpoints such as `/tasks` and `/quests`.

macOS/Linux equivalent:

```bash
export DB_USER="your_db_user"
export DB_PASSWORD="your_db_password"
export DB_DSN="your_db_dsn"
```

Without these DB variables, the root endpoint `/` can still run, but DB-backed endpoints may fail when they try to connect to Oracle.

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
