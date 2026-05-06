from fastapi import Depends, FastAPI
from fastapi.responses import RedirectResponse
from services.task_service import create_task,get_tasks
from services.quest_service import get_quests
from services.ai_service import enrich_task
from services.task_service import complete_task
from services.filesystem_user_service import (
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
from services.user_context import current_local_user_id, current_oracle_user_id
from routes.insights_routes import router as insights_router
from routes.missions_routes import router as missions_router
from routes.overview_routes import router as overview_router
from routes.standup_routes import router as standup_router
from routes.focus_routes import router as focus_router
from routes.quests_routes import router as quests_router
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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
        "name": "Missions",
        "description": "Generate AI mission recommendations without mutating working-today state.",
    },
    {
        "name": "Auth",
        "description": "Local filesystem login and profile creation.",
    },
    {
        "name": "Users",
        "description": "Read local user profile details.",
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

app=FastAPI(
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
    allow_origins=["*"],  # allow all origins (OK for local dev)
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

@app.get("/", tags=["Health"])
def root(): return {"msg":"DevQuest Pro"}

@app.get("/swagger", include_in_schema=False)
def swagger_redirect():
    return RedirectResponse(url="/docs")

@app.get("/tasks", tags=["Tasks"])
def tasks(user_id: int = Depends(current_oracle_user_id)): return get_tasks(user_id)

@app.get("/quests", tags=["Quests"])
def quests(user_id: int = Depends(current_oracle_user_id)): return get_quests(user_id)

@app.get("/api/v1/capacity", tags=["Dashboard"])
def capacity(date: str | None = None, user_id: int = Depends(current_oracle_user_id)): return capacity_response(date, user_id)

@app.get("/api/v1/dashboard/today", tags=["Dashboard"])
def dashboard_today(date: str | None = None, user_id: int = Depends(current_oracle_user_id)): return dashboard_today_response(date, user_id)

@app.post("/tasks", tags=["Tasks"])
async def add_task(task:TaskCreate, user_id: int = Depends(current_oracle_user_id)):
    task_payload=task.model_dump()
    ai=await enrich_task(task_payload["title"],task_payload["description"])
    return create_task(task_payload,ai,user_id)

@app.post("/tasks/{task_id}/complete", tags=["Tasks"])
def mark_complete(task_id: str, user_id: int = Depends(current_oracle_user_id)):
    return complete_task(task_id,user_id)

@app.post("/api/v1/auth/register", tags=["Auth"])
def register_filesystem_user(payload: dict):
    return register_user(payload)

@app.post("/api/v1/auth/login", tags=["Auth"])
def login_filesystem_user(payload: dict):
    return login_user(payload)

@app.post("/api/v1/auth/logout", tags=["Auth"])
def logout_filesystem_user(user_id: str = Depends(current_local_user_id)):
    return logout_user(user_id)

@app.get("/api/v1/users/profile", tags=["Users"])
def filesystem_user_profile(identifier: str):
    return get_user_profile(identifier)

@app.post("/api/v1/tasks")
def add_oracle_task(task: dict, user_id: int = Depends(current_oracle_user_id)):
    return create_oracle_task(task, user_id)

@app.get("/api/v1/tasks")
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
            "page": page,
            "page_size": page_size,
        },
        user_id,
    )

@app.get("/api/v1/tasks/{task_id}")
def oracle_task_detail(task_id: str, user_id: int = Depends(current_oracle_user_id)):
    return get_oracle_task(task_id, user_id)

@app.patch("/api/v1/tasks/{task_id}")
def patch_oracle_task(task_id: str, payload: dict, user_id: int = Depends(current_oracle_user_id)):
    return update_oracle_task(task_id, payload, user_id)

@app.put("/api/v1/tasks/{task_id}/notes")
def update_oracle_notes(task_id: str, payload: dict, user_id: int = Depends(current_oracle_user_id)):
    return update_oracle_task_notes(task_id, payload, user_id)

@app.patch("/api/v1/tasks/{task_id}/status")
def patch_oracle_status(task_id: str, payload: dict, user_id: int = Depends(current_oracle_user_id)):
    return update_oracle_task_status(task_id, payload, user_id)

@app.post("/api/v1/tasks/{task_id}/complete")
def complete_oracle_status(task_id: str, payload: dict, user_id: int = Depends(current_oracle_user_id)):
    return complete_oracle_task(task_id, payload, user_id)

@app.put("/api/v1/tasks/{task_id}/today")
def update_oracle_today(task_id: str, payload: dict, user_id: int = Depends(current_oracle_user_id)):
    return update_oracle_task_today(task_id, payload, user_id)
