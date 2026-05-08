# 🚀 DevQuest

DevQuest is an AI-assisted, gamified productivity dashboard for developers. It brings tasks, meetings, focus time, daily missions, quests, XP, standup notes, and productivity overviews into one workspace so a developer can quickly decide what to work on next and explain progress clearly.

The app is built for the hackathon flow where work is scattered across task systems, calendar meetings, notes, and local context. DevQuest turns that raw context into a focused plan for the day.

## ✨ What DevQuest Does

| Area | What it provides |
| --- | --- |
| 🧭 Dashboard | Today's missions, working-today tasks, schedule, focus time, XP, meetings, and daily KPI cards. |
| ✅ My Tasks | Create, update, filter, enrich, and complete work items with XP, priority, notes, RCA sizing, and working-today state. |
| ✨ AI Insights | Generate AI-backed task insights, risks, recommendations, focus guidance, and standup context. |
| 🏁 Quests | Convert prioritized work into mission-style quest plans based on impact, effort, XP, due dates, and available capacity. |
| 🎯 Focus Mode | Track focused work sessions and use them for XP, progress, and daily summaries. |
| 📊 Overviews | Generate daily and weekly summaries from completed work, meetings, notes, blockers, and focus activity. |
| 🏆 Progress | XP, streaks, levels, and reward-style feedback for consistent execution. |

## 🤖 AI Usage

DevQuest uses AI as a planning and summarization layer, while keeping core metrics deterministic in the backend.

- AI suggests mission order using task priority, due dates, XP, impact, effort, blockers, notes, and available focus capacity.
- AI Insights explain what needs attention, why it matters, what risks exist, and what the next practical actions should be.
- Standup and overview generation use task, focus, calendar, and note evidence instead of asking the user to manually assemble updates.
- If AI is unavailable, backend services keep the app usable through deterministic scoring and fallback behavior.

## 🧱 Architecture

```text
React frontend
    |
    | HTTP / JSON
    v
FastAPI backend
    |
    | Repository and service layer
    v
Oracle Autonomous Database

OCI Generative AI is used by backend AI services when real AI mode is enabled.
```

### 🛠️ Main Tech

- Frontend: React, Create React App, CSS modules/files, Lucide icons, Recharts.
- Backend: Python, FastAPI, Pydantic-style request validation, Oracle DB access through `oracledb`.
- Database: Oracle Autonomous Database using the `DEVQUEST_APP` schema.
- AI: OCI Generative AI through OCI SDK configuration.
- Local docs: FastAPI Swagger UI, ReDoc, and markdown implementation notes.

## ⚡ Quick Start

For the integrated local app, use the checked-in launcher:

```powershell
.\start-devquest.cmd
```

This script starts the backend on port `8000`, serves the production frontend on port `3000`, and opens the app in the browser.

Open:

- 🖥️ App: `http://127.0.0.1:3000`
- ⚙️ Backend: `http://127.0.0.1:8000`
- 📘 Swagger UI: `http://127.0.0.1:8000/docs`
- 📗 Swagger shortcut: `http://127.0.0.1:8000/swagger`
- 📕 ReDoc: `http://127.0.0.1:8000/redoc`
- 🧾 OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

To stop the app:

```powershell
.\stop-devquest.cmd
```

## 📦 Production Frontend Build

To build only the frontend production bundle:

```powershell
.\build-devquest-prod.ps1
```

Or run directly from the frontend folder:

```powershell
cd frontend
npm run build
```

The production build is written to `frontend/build`.

## 🧑‍💻 Manual Developer Setup

### 🐍 Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

### ⚛️ Frontend

```powershell
cd frontend
npm install
npm start
```

Use `npm start` for the React development server. Use `npm run build` or `build-devquest-prod.ps1` for the production bundle.

## 🔀 Runtime Modes

The app supports environment-based runtime selection so teammates can run the same code with local fallback behavior or real services.

| Variable | Common value | Purpose |
| --- | --- | --- |
| 🗄️ `DEVQUEST_DATA_MODE` | `oracle` | Use Oracle ADB repositories. |
| 🤖 `DEVQUEST_AI_MODE` | `real` | Use configured OCI GenAI provider. |
| 🔌 `DEVQUEST_AI_PROVIDER` | `oci_genai` | Select OCI GenAI integration. |
| 🔐 `OCI_AUTH_TYPE` | `config_file` or `security_token` | Select OCI SDK authentication path. |
| 👤 `OCI_CONFIG_PROFILE` | `boat` or team profile name | OCI profile used for GenAI calls. |
| 🧭 `OCI_COMPARTMENT_ID` | Team compartment OCID | Compartment for GenAI inference. |
| 🧠 `OCI_GENAI_MODEL_ID` | Team-selected model ID | Model used for AI generation. |
| 🏊 `DB_POOL_SIZE` | `10` | Default Oracle connection pool sizing. |

See `docs/oci-genai-team-setup.md` and `docs/oracle-db-wallet-setup.md` for full local setup details.

## 📚 Useful Documentation

| Doc | Purpose |
| --- | --- |
| `docs/local-start.md` | Local service startup, links, Swagger, and ReDoc notes. |
| `docs/backend-api-integration-plan.md` | Backend API contracts, schemas, and integration plan. |
| `docs/backend-todo-list.md` | Phase checklist and database schema notes. |
| `docs/oracle-db-wallet-setup.md` | Oracle ADB wallet and local database setup. |
| `docs/oci-genai-team-setup.md` | OCI GenAI setup, auth modes, model notes, and validation prompts. |
| `docs/phase-8-dashboard-capacity-spec.md` | Dashboard and capacity API behavior. |
| `docs/phase-12-missions-quests-implementation.md` | Missions and quests implementation notes. |
| `docs/phase-13-ai-insights-implementation.md` | AI insights endpoint details. |
| `docs/ai-usage-impact-summary.md` | Submission-ready AI usage and impact summary. |
| `docs/demo-ai-insights-missions-talking-points.md` | Live demo talking points for AI Insights and Missions. |

## 🔗 API Highlights

Common local endpoints:

- `GET /api/v1/tasks`
- `POST /api/v1/tasks`
- `GET /api/v1/dashboard/today?date=YYYY-MM-DD`
- `GET /api/v1/capacity?date=YYYY-MM-DD`
- `GET /api/v1/quests/today?date=YYYY-MM-DD`
- `POST /api/v1/quests/today/generate`
- `GET /api/v1/insights/today?date=YYYY-MM-DD`
- `POST /api/v1/insights/today/generate`
- `GET /api/v1/overviews/daily?date=YYYY-MM-DD`
- `POST /api/v1/overviews/daily/generate`
- `GET /api/v1/overviews/weekly?week_start=YYYY-MM-DD`
- `POST /api/v1/overviews/weekly/generate`

For the full request and response shape, use Swagger UI at `http://127.0.0.1:8000/docs`.

## ✅ Validation

Frontend build:

```powershell
cd frontend
npm run build
```

Backend smoke check:

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/tasks" -UseBasicParsing
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/dashboard/today?date=2026-05-07" -UseBasicParsing
```

## 🤝 Team Notes

- 🧹 Keep generated logs out of commits: `backend/uvicorn*.log` and `frontend/static-server*.log`.
- 🏊 Prefer the shared Oracle connection pool helpers instead of opening standalone DB connections in service code.
- 👤 Keep user-specific queries scoped by dynamic user ID, not hardcoded IDs.
- 🌐 Store and compare work dates in UTC where backend APIs expect UTC date semantics.
- 📝 Use docs in `docs/` when adding or changing API behavior so other teammates and AI agents can follow the contract.
