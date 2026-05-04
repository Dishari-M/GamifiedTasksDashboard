from fastapi import FastAPI
from services.task_service import create_task,get_tasks
from services.quest_service import get_quests
from services.ai_service import enrich_task
from services.task_service import complete_task
from services.filesystem_task_service import (
    complete_filesystem_task,
    create_filesystem_task,
    get_filesystem_task,
    list_filesystem_tasks,
    update_filesystem_task,
    update_filesystem_task_notes,
    update_filesystem_task_status,
    update_filesystem_task_today,
)
from fastapi.middleware.cors import CORSMiddleware

app=FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all origins (OK for local dev)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root(): return {"msg":"DevQuest Pro"}

@app.get("/tasks")
def tasks(): return get_tasks()

@app.get("/quests")
def quests(): return get_quests()

@app.post("/tasks")
async def add_task(task:dict):
    ai=await enrich_task(task["title"],task["description"])
    return create_task(task,ai)

@app.post("/tasks/{task_id}/complete")
def mark_complete(task_id: str):
    return complete_task(task_id)

@app.post("/api/v1/tasks")
def add_filesystem_task(task: dict):
    return create_filesystem_task(task)

@app.get("/api/v1/tasks")
def filesystem_tasks(
    status: str | None = None,
    source: str | None = None,
    external_source: str | None = None,
    priority: str | None = None,
    working_today: bool | None = None,
    completed_date: str | None = None,
    completed_from: str | None = None,
    completed_to: str | None = None,
    search: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    return list_filesystem_tasks(
        {
            "status": status,
            "source": source,
            "external_source": external_source,
            "priority": priority,
            "working_today": working_today,
            "completed_date": completed_date,
            "completed_from": completed_from,
            "completed_to": completed_to,
            "search": search,
            "q": q,
            "page": page,
            "page_size": page_size,
        }
    )

@app.get("/api/v1/tasks/{task_id}")
def filesystem_task_detail(task_id: str):
    return get_filesystem_task(task_id)

@app.patch("/api/v1/tasks/{task_id}")
def patch_filesystem_task(task_id: str, payload: dict):
    return update_filesystem_task(task_id, payload)

@app.put("/api/v1/tasks/{task_id}/notes")
def update_filesystem_notes(task_id: str, payload: dict):
    return update_filesystem_task_notes(task_id, payload)

@app.patch("/api/v1/tasks/{task_id}/status")
def patch_filesystem_status(task_id: str, payload: dict):
    return update_filesystem_task_status(task_id, payload)

@app.post("/api/v1/tasks/{task_id}/complete")
def complete_filesystem_status(task_id: str, payload: dict):
    return complete_filesystem_task(task_id, payload)

@app.put("/api/v1/tasks/{task_id}/today")
def update_filesystem_today(task_id: str, payload: dict):
    return update_filesystem_task_today(task_id, payload)
