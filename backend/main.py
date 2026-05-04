from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from services.task_service import create_task,get_tasks
from services.quest_service import get_quests
from services.ai_service import enrich_task
from services.task_service import complete_task
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

@app.get("/", tags=["Health"])
def root(): return {"msg":"DevQuest Pro"}

@app.get("/swagger", include_in_schema=False)
def swagger_redirect():
    return RedirectResponse(url="/docs")

@app.get("/tasks", tags=["Tasks"])
def tasks(): return get_tasks()

@app.get("/quests", tags=["Quests"])
def quests(): return get_quests()

@app.post("/tasks", tags=["Tasks"])
async def add_task(task:TaskCreate):
    task_payload=task.model_dump()
    ai=await enrich_task(task_payload["title"],task_payload["description"])
    return create_task(task_payload,ai)

@app.post("/tasks/{task_id}/complete", tags=["Tasks"])
def mark_complete(task_id: str):
    return complete_task(task_id)
