from fastapi import FastAPI
from services.task_service import create_task,get_tasks
from services.quest_service import get_quests
from services.ai_service import enrich_task
from services.task_service import complete_task
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
