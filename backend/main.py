from __future__ import annotations

import importlib.util
import os
import traceback
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from routes.overview_routes import router as overview_router
from routes.work_dates_routes import router as work_dates_router
from services.ai_service import enrich_task
from services.phase8_capacity_service import capacity_response
from services.phase8_dashboard_service import dashboard_today_response
from services.quest_service import get_quests
from services.task_service import complete_task, create_task, get_tasks


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


class JiraRcaResponse(BaseModel):
    jira_key: str
    root_cause_analysis: str
    elapsed_seconds: float


class JiraRcaJobResponse(BaseModel):
    job_id: str
    jira_key: str
    status: str
    logs: list[str]
    result: dict | None = None
    error: str = ""
    started_at: float | None = None


class JiraOneLineDescriptionRequest(BaseModel):
    jira_key: str = Field(..., examples=["HEPRT-123"])


class JiraOneLineDescriptionResponse(BaseModel):
    jira_key: str
    one_liner_description: str
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
        "name": "Dashboard",
        "description": "Phase 8 dashboard summary and capacity APIs.",
    },
    {
        "name": "Overviews",
        "description": "Daily and weekly productivity overviews with AI-generated insights.",
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
app.include_router(work_dates_router)


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
def tasks():
    return get_tasks()


@app.get("/quests", tags=["Quests"])
def quests():
    return get_quests()


@app.get("/api/v1/capacity", tags=["Dashboard"])
def capacity(date: str | None = None):
    return capacity_response(date)


@app.get("/api/v1/dashboard/today", tags=["Dashboard"])
def dashboard_today(date: str | None = None):
    return dashboard_today_response(date)


@app.post("/tasks", tags=["Tasks"])
async def add_task(task: TaskCreate):
    task_payload = task.model_dump()
    ai = await enrich_task(task_payload["title"], task_payload["description"])
    return create_task(task_payload, ai)


@app.post("/tasks/{task_id}/complete", tags=["Tasks"])
def mark_complete(task_id: str):
    return complete_task(task_id)


@app.post("/api/jira/rca", response_model=JiraRcaResponse, tags=["Jira RCA"])
async def jira_rca(req: JiraRcaRequest, x_api_key: str | None = Header(default=None)) -> JiraRcaResponse:
    verify_api_key(x_api_key)
    jira_key = codex_config.normalize_jira_key(req.jira_key)

    try:
        start = perf_counter()
        rca_output = await codex_config.run_codex_async(
            codex_config.build_jira_rca_prompt(jira_key, req.additional_context)
        )
        if codex_config.looks_like_mcp_auth_cancelled(rca_output):
            codex_config.raise_mcp_auth_required(jira_key)

        return JiraRcaResponse(
            jira_key=jira_key,
            root_cause_analysis=rca_output,
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
async def start_jira_rca_job(req: JiraRcaRequest, x_api_key: str | None = Header(default=None)) -> dict:
    verify_api_key(x_api_key)
    try:
        return codex_config.start_rca_job(req.jira_key, req.additional_context)
    except HTTPException:
        raise
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to start Jira RCA job: {exc}")


@app.get("/api/jira/rca/jobs/{job_id}", response_model=JiraRcaJobResponse, tags=["Jira RCA"])
async def get_jira_rca_job(job_id: str, x_api_key: str | None = Header(default=None)) -> dict:
    verify_api_key(x_api_key)
    return codex_config.get_rca_job(job_id)


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
