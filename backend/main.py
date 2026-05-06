from __future__ import annotations

import importlib.util
import os
import traceback
from pathlib import Path
from time import perf_counter

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from routes.focus_routes import router as focus_router
from routes.insights_routes import router as insights_router
from routes.missions_routes import router as missions_router
from routes.overview_routes import router as overview_router
from routes.quests_routes import router as quests_router
from routes.standup_routes import router as standup_router
from services.ai_service import enrich_task
from services.oracle_user_service import (
    get_user_profile,
    login_user,
    logout_user,
    register_user,
)
from services.oracle_task_service import (
    complete_oracle_task,
    create_oracle_task,
    get_oracle_task,
    list_oracle_tasks,
    update_oracle_task,
    update_oracle_task_notes,
    update_oracle_task_status,
    update_oracle_task_today,
)
from services.phase8_capacity_service import capacity_response
from services.phase8_dashboard_service import dashboard_today_response
from services.quest_service import get_quests
from services.sync_service import (
    fetch_outlook_calendar_events,
    latest_sync_run,
    list_calendar_events,
    list_removed_calendar_events,
    remove_calendar_event,
    restore_calendar_event,
    run_sync,
    update_calendar_event,
)
from services.task_service import complete_task, create_task, get_tasks
from services.user_context import current_local_user_id, current_oracle_user_id


SERVICE_DIR = Path(__file__).resolve().parent
CODEX_CONFIG_PATH = SERVICE_DIR / "codex-config.py"
API_KEY = os.getenv("JIRA_RCA_API_KEY", os.getenv("AI_REVIEW_API_KEY", "")).strip()


def load_codex_config():
    spec = importlib.util.spec_from_file_location("codex_config", CODEX_CONFIG_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load Codex config module: {CODEX_CONFIG_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


codex_config = load_codex_config()


class JiraRcaRequest(BaseModel):
    jira_key: str = Field(..., examples=["HEPRT-123"])
    additional_context: str = Field(
        default="",
        description="Optional logs, reproduction notes, screenshots text, or extra hints to include in the RCA.",
    )
    priority: str | None = Field(default=None, examples=["High"])
    code_base_path: str | None = Field(
        default=None,
        description="Optional local workspace or codebase directory where RCA should analyze source files.",
    )


class JiraRcaResponse(BaseModel):
    jira_key: str
    root_cause_analysis: str
    jira_tshirt_sizing: dict
    elapsed_seconds: float


class JiraRcaJobResponse(BaseModel):
    job_id: str
    jira_key: str
    code_base_path: str | None = None
    status: str
    logs: list[str]
    result: dict | None = None
    error: str = ""
    started_at: float | None = None


class JiraRcaWorkspaceSelectRequest(BaseModel):
    initial_path: str | None = None


class JiraRcaWorkspaceSelectResponse(BaseModel):
    code_base_path: str


class JiraOneLineDescriptionRequest(BaseModel):
    jira_key: str = Field(..., examples=["HEPRT-123"])


class JiraOneLineDescriptionResponse(BaseModel):
    jira_key: str
    one_liner_description: str
    elapsed_seconds: float


class JiraTaskFieldsResponse(BaseModel):
    jira_key: str
    title: str
    description: str
    priority: str
    labels: list[str]
    type: str
    elapsed_seconds: float


class JiraSsoLoginRequest(BaseModel):
    jira_key: str = Field(..., examples=["HEPRT-123"])


class JiraSsoLoginResponse(BaseModel):
    jira_key: str
    message: str
    process_id: int | None = None

class TaskCreate(BaseModel):
    title: str = Field(..., examples=["Fix payment gateway timeout issue"])
    description: str = Field(..., examples=["Users face timeout while making payments on checkout."])
    priority: str = Field(..., examples=["High"])


tags_metadata = [
    {
        "name": "Health",
        "description": "Local service health and documentation discovery.",
    },
    {
        "name": "Tasks",
        "description": "Create, list, and complete DevQuest work items.",
    },
    {
        "name": "Quests",
        "description": "Read prioritized daily quest recommendations.",
    },
    {
        "name": "Jira RCA",
        "description": "Fetch Jira details through MCP and run Codex-powered root cause analysis.",
    },
    {
        "name": "Missions",
        "description": "Generate AI mission recommendations without mutating working-today state.",
    },
    {
        "name": "Auth",
        "description": "Oracle-backed login and profile creation.",
    },
    {
        "name": "Users",
        "description": "Read Oracle-backed user profile details.",
    },
    {
        "name": "Dashboard",
        "description": "Phase 8 dashboard summary and capacity APIs.",
    },
    {
        "name": "Overviews",
        "description": "Daily and weekly productivity overviews with AI-generated insights.",
    },
    {
        "name": "Insights",
        "description": "AI-generated daily risks, recommendations, and task insights.",
    },
]

app = FastAPI(
    title="DevQuest API",
    description="Local API for the DevQuest gamified developer productivity dashboard.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=tags_metadata,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(overview_router)
app.include_router(standup_router)
app.include_router(insights_router)
app.include_router(missions_router)
app.include_router(quests_router)
app.include_router(focus_router)


def verify_api_key(x_api_key: str | None) -> None:
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/", tags=["Health"])
def root():
    return {"msg": "DevQuest Pro"}


@app.get("/swagger", include_in_schema=False)
def swagger_redirect():
    return RedirectResponse(url="/docs")


@app.get("/api/jira/health", tags=["Jira RCA"])
async def jira_rca_healthcheck() -> dict[str, str]:
    return {
        **codex_config.get_health_details(),
        "api_key_required": str(bool(API_KEY)).lower(),
    }


@app.get("/tasks", tags=["Tasks"])
def tasks(user_id: int = Depends(current_oracle_user_id)):
    return get_tasks(user_id)


@app.get("/quests", tags=["Quests"])
def quests(user_id: int = Depends(current_oracle_user_id)):
    return get_quests(user_id)


@app.get("/api/v1/capacity", tags=["Dashboard"])
def capacity(date: str | None = None, user_id: int = Depends(current_oracle_user_id)):
    return capacity_response(date, user_id)


@app.get("/api/v1/dashboard/today", tags=["Dashboard"])
def dashboard_today(date: str | None = None, user_id: int = Depends(current_oracle_user_id)):
    return dashboard_today_response(date, user_id)


@app.post("/tasks", tags=["Tasks"])
async def add_task(task: TaskCreate, user_id: int = Depends(current_oracle_user_id)):
    task_payload = task.model_dump()
    ai = await enrich_task(task_payload["title"], task_payload["description"])
    return create_task(task_payload, ai, user_id)


@app.post("/tasks/{task_id}/complete", tags=["Tasks"])
def mark_complete(task_id: str, user_id: int = Depends(current_oracle_user_id)):
    return complete_task(task_id, user_id)


@app.post("/api/jira/rca", response_model=JiraRcaResponse, tags=["Jira RCA"])
async def jira_rca(
    req: JiraRcaRequest,
    x_api_key: str | None = Header(default=None),
    x_devquest_user_id: str | None = Header(default=None, alias="X-DevQuest-User-Id"),
) -> JiraRcaResponse:
    verify_api_key(x_api_key)
    jira_key = codex_config.normalize_jira_key(req.jira_key)

    try:
        start = perf_counter()
        rca_output = await codex_config.run_codex_async(
            codex_config.build_jira_rca_prompt(jira_key, req.additional_context, req.code_base_path),
            req.code_base_path,
        )
        if codex_config.looks_like_mcp_auth_cancelled(rca_output):
            codex_config.raise_mcp_auth_required(jira_key)

        tshirt_sizing = codex_config.build_jira_tshirt_sizing(
            jira_key,
            rca_output,
            user_id=x_devquest_user_id or codex_config.LOCAL_USER_ID,
            priority=req.priority,
        )
        return JiraRcaResponse(
            jira_key=jira_key,
            root_cause_analysis=rca_output,
            jira_tshirt_sizing=tshirt_sizing,
            elapsed_seconds=perf_counter() - start,
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except codex_config.subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Codex CLI timed out while processing the Jira RCA.")
    except HTTPException:
        raise
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Jira RCA failed: {exc}")


@app.post("/api/jira/rca/jobs", response_model=JiraRcaJobResponse, tags=["Jira RCA"])
async def start_jira_rca_job(
    req: JiraRcaRequest,
    x_api_key: str | None = Header(default=None),
    x_devquest_user_id: str | None = Header(default=None, alias="X-DevQuest-User-Id"),
) -> dict:
    verify_api_key(x_api_key)
    try:
        return codex_config.start_rca_job(
            req.jira_key,
            req.additional_context,
            user_id=x_devquest_user_id or codex_config.LOCAL_USER_ID,
            priority=req.priority,
            code_base_path=req.code_base_path,
        )
    except HTTPException:
        raise
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to start Jira RCA job: {exc}")


@app.get("/api/jira/rca/jobs/{job_id}", response_model=JiraRcaJobResponse, tags=["Jira RCA"])
async def get_jira_rca_job(job_id: str, x_api_key: str | None = Header(default=None)) -> dict:
    verify_api_key(x_api_key)
    return codex_config.get_rca_job(job_id)


@app.post("/api/jira/rca/jobs/{job_id}/cancel", response_model=JiraRcaJobResponse, tags=["Jira RCA"])
async def cancel_jira_rca_job(job_id: str, x_api_key: str | None = Header(default=None)) -> dict:
    verify_api_key(x_api_key)
    return codex_config.cancel_rca_job(job_id)


@app.post("/api/jira/rca/workspace/select", response_model=JiraRcaWorkspaceSelectResponse, tags=["Jira RCA"])
def select_jira_rca_workspace(
    req: JiraRcaWorkspaceSelectRequest | None = None,
    x_api_key: str | None = Header(default=None),
) -> JiraRcaWorkspaceSelectResponse:
    verify_api_key(x_api_key)
    try:
        selected_path = codex_config.select_rca_workspace_folder((req or JiraRcaWorkspaceSelectRequest()).initial_path)
        return JiraRcaWorkspaceSelectResponse(code_base_path=selected_path)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not open the local folder picker. Start the local Codex runner/backend on your machine "
                f"and try again. {exc}"
            ),
        )


@app.post("/api/jira/one-line-description", response_model=JiraOneLineDescriptionResponse, tags=["Jira RCA"])
async def jira_one_line_description(
    req: JiraOneLineDescriptionRequest,
    x_api_key: str | None = Header(default=None),
) -> JiraOneLineDescriptionResponse:
    verify_api_key(x_api_key)
    jira_key = codex_config.normalize_jira_key(req.jira_key)

    try:
        start = perf_counter()
        description_output = await codex_config.run_codex_async(
            codex_config.build_jira_one_line_description_prompt(jira_key)
        )
        if codex_config.looks_like_mcp_auth_cancelled(description_output):
            codex_config.raise_mcp_auth_required(jira_key)

        return JiraOneLineDescriptionResponse(
            jira_key=jira_key,
            one_liner_description=codex_config.normalize_one_line_description(description_output),
            elapsed_seconds=perf_counter() - start,
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except codex_config.subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Codex CLI timed out while fetching the Jira description.")
    except HTTPException:
        raise
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Jira one-line description failed: {exc}")


@app.post("/api/jira/task-fields", response_model=JiraTaskFieldsResponse, tags=["Jira RCA"])
async def jira_task_fields(
    req: JiraOneLineDescriptionRequest,
    x_api_key: str | None = Header(default=None),
) -> JiraTaskFieldsResponse:
    verify_api_key(x_api_key)
    jira_key = codex_config.normalize_jira_key(req.jira_key)

    try:
        start = perf_counter()
        fields_output = await codex_config.run_codex_async(
            codex_config.build_jira_task_fields_prompt(jira_key)
        )
        if codex_config.looks_like_mcp_auth_cancelled(fields_output):
            codex_config.raise_mcp_auth_required(jira_key)

        fields = codex_config.normalize_jira_task_fields(jira_key, fields_output)
        return JiraTaskFieldsResponse(
            **fields,
            elapsed_seconds=perf_counter() - start,
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except codex_config.subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Codex CLI timed out while fetching the Jira task fields.")
    except HTTPException:
        raise
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Jira task field fetch failed: {exc}")


@app.post("/api/jira/sso-login", response_model=JiraSsoLoginResponse, tags=["Jira RCA"])
async def jira_sso_login(req: JiraSsoLoginRequest, x_api_key: str | None = Header(default=None)) -> JiraSsoLoginResponse:
    verify_api_key(x_api_key)
    jira_key = codex_config.normalize_jira_key(req.jira_key)

    try:
        process = codex_config.start_jira_sso_session(jira_key)
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to start Jira SSO Codex session: {exc}")

    return JiraSsoLoginResponse(
        jira_key=jira_key,
        message="A visible Codex session was started for Jira SSO. Complete the browser sign-in, then retry Generate by AI.",
        process_id=process.pid,
    )


current_user_id = current_local_user_id


@app.get("/api/v1/calendar/events", tags=["Calendar"])
def filesystem_calendar_events(date: str | None = None, user_id: str = Depends(current_user_id)):
    return {
        "items": list_calendar_events(date, user_id),
        "removed_items": list_removed_calendar_events(date, user_id),
    }


@app.delete("/api/v1/calendar/events/{event_id}", tags=["Calendar"])
def delete_filesystem_calendar_event(event_id: str, user_id: str = Depends(current_user_id)):
    return remove_calendar_event(event_id, user_id)


@app.post("/api/v1/calendar/events/{event_id}/restore", tags=["Calendar"])
def restore_filesystem_calendar_event(event_id: str, user_id: str = Depends(current_user_id)):
    return restore_calendar_event(event_id, user_id)


@app.patch("/api/v1/calendar/events/{event_id}", tags=["Calendar"])
def patch_filesystem_calendar_event(event_id: str, payload: dict, user_id: str = Depends(current_user_id)):
    return update_calendar_event(event_id, user_id, payload)


@app.post("/api/v1/calendar/events/fetch", tags=["Calendar"])
async def fetch_filesystem_calendar_events(payload: dict, user_id: str = Depends(current_user_id)):
    return await fetch_outlook_calendar_events(codex_config, user_id, (payload or {}).get("date"))


@app.post("/api/v1/auth/register", tags=["Auth"])
def register_oracle_user(payload: dict):
    return register_user(payload)


@app.post("/api/v1/auth/login", tags=["Auth"])
def login_oracle_user(payload: dict):
    return login_user(payload)


@app.post("/api/v1/auth/logout", tags=["Auth"])
def logout_oracle_user(user_id: str = Depends(current_local_user_id)):
    return logout_user(user_id)


@app.get("/api/v1/users/profile", tags=["Users"])
def oracle_user_profile(identifier: str):
    return get_user_profile(identifier)

@app.post("/api/v1/tasks", tags=["Tasks"])
def add_oracle_task(task: dict, user_id: int = Depends(current_oracle_user_id)):
    return create_oracle_task(task, user_id)


@app.get("/api/v1/tasks", tags=["Tasks"])
def oracle_tasks(
    status: str | None = None,
    source: str | None = None,
    external_source: str | None = None,
    priority: str | None = None,
    working_today: bool | None = None,
    worked_date: str | None = None,
    completed_date: str | None = None,
    completed_from: str | None = None,
    completed_to: str | None = None,
    search: str | None = None,
    q: str | None = None,
    include_total: bool = True,
    page: int = 1,
    page_size: int = 50,
    user_id: int = Depends(current_oracle_user_id),
):
    return list_oracle_tasks(
        {
            "status": status,
            "source": source,
            "external_source": external_source,
            "priority": priority,
            "working_today": working_today,
            "worked_date": worked_date,
            "completed_date": completed_date,
            "completed_from": completed_from,
            "completed_to": completed_to,
            "search": search,
            "q": q,
            "include_total": include_total,
            "page": page,
            "page_size": page_size,
        },
        user_id,
    )


@app.get("/api/v1/tasks/{task_id}", tags=["Tasks"])
def oracle_task_detail(task_id: str, user_id: int = Depends(current_oracle_user_id)):
    return get_oracle_task(task_id, user_id)


@app.patch("/api/v1/tasks/{task_id}", tags=["Tasks"])
def patch_oracle_task(task_id: str, payload: dict, user_id: int = Depends(current_oracle_user_id)):
    return update_oracle_task(task_id, payload, user_id)


@app.put("/api/v1/tasks/{task_id}/notes", tags=["Tasks"])
def update_oracle_notes(task_id: str, payload: dict, user_id: int = Depends(current_oracle_user_id)):
    return update_oracle_task_notes(task_id, payload, user_id)


@app.patch("/api/v1/tasks/{task_id}/status", tags=["Tasks"])
def patch_oracle_status(task_id: str, payload: dict, user_id: int = Depends(current_oracle_user_id)):
    return update_oracle_task_status(task_id, payload, user_id)


@app.post("/api/v1/tasks/{task_id}/complete", tags=["Tasks"])
def complete_oracle_status(task_id: str, payload: dict, user_id: int = Depends(current_oracle_user_id)):
    return complete_oracle_task(task_id, payload, user_id)


@app.put("/api/v1/tasks/{task_id}/today", tags=["Tasks"])
def update_oracle_today(task_id: str, payload: dict, user_id: int = Depends(current_oracle_user_id)):
    return update_oracle_task_today(task_id, payload, user_id)


@app.post("/api/v1/sync/run", tags=["Sync"])
async def run_filesystem_sync(payload: dict | None = None, user_id: str = Depends(current_user_id)):
    return await run_sync(codex_config, user_id, (payload or {}).get("sources"))


@app.get("/api/v1/sync/runs", tags=["Sync"])
def filesystem_sync_runs(user_id: str = Depends(current_user_id)):
    return latest_sync_run(user_id)
