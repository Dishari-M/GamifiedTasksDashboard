from datetime import datetime, timezone
from uuid import uuid4

from config import get_oci_genai_model_id
from services.filesystem_store import read_records, with_store_lock, write_records
from services.insights_ai_service import TODAY_INSIGHT_SYSTEM_PROMPT, build_today_insight_ai_output
from services.phase8_capacity_service import build_capacity
from services.phase8_data_provider import get_calendar_events, resolve_work_date
from services.stat_insight_service import build_stat_insights, previous_date_key


WORK_ITEMS_FILE = "work_items.json"
AI_RUNS_FILE = "ai_runs.json"
RUN_TYPE = "TODAY_INSIGHT"


def today_insight_response(date=None, user_id=None):
    work_date = resolve_work_date(date)
    return {"data": get_today_insight(work_date, user_id), "meta": {"request_id": str(uuid4())}}


def generate_today_insight_response(payload, user_id=None):
    work_date = resolve_work_date(payload.date)
    return {
        "data": generate_today_insight(work_date, user_id, payload.model_dump()),
        "meta": {"request_id": str(uuid4())},
    }


def get_today_insight(work_date, user_id):
    def action():
        context = _context(work_date, user_id)
        saved = _latest_successful_run(read_records(AI_RUNS_FILE), user_id, work_date)
        ai = saved.get("response_payload") if saved else _fallback_ai(context)
        return _response(context, ai, saved.get("ai_run_id") if saved else None)

    return with_store_lock(action)


def generate_today_insight(work_date, user_id, request_payload):
    def action():
        ai_runs = read_records(AI_RUNS_FILE)
        context = _context(work_date, user_id)

        if not request_payload.get("force"):
            saved = _latest_successful_run(ai_runs, user_id, work_date)
            if saved:
                return _response(context, saved.get("response_payload") or {}, saved.get("ai_run_id"))

        ai_run = _create_ai_run(ai_runs, user_id, work_date, context, request_payload)
        write_records(AI_RUNS_FILE, ai_runs)

        try:
            ai = build_today_insight_ai_output(context)
        except Exception as exc:
            _mark_ai_run_failed(ai_runs, ai_run["ai_run_id"], exc)
            write_records(AI_RUNS_FILE, ai_runs)
            raise

        _mark_ai_run_succeeded(ai_runs, ai_run["ai_run_id"], ai)
        write_records(AI_RUNS_FILE, ai_runs)
        return _response(context, ai, ai_run["ai_run_id"])

    return with_store_lock(action)


def _context(work_date, user_id):
    tasks = [_response_task(task, work_date) for task in read_records(WORK_ITEMS_FILE) if task.get("user_id") == user_id]
    previous_date = previous_date_key(work_date)
    worked_tasks = [task for task in tasks if task["working_today"]]
    completed_tasks = [task for task in tasks if _date_part(task.get("completed_at")) == work_date]
    previous_worked_tasks = [task for task in tasks if task.get("status") != "Done" and previous_date in _worked_dates(task.get("worked_dates"))]
    previous_completed_tasks = [task for task in tasks if _date_part(task.get("completed_at")) == previous_date]
    sorted_worked = sorted(
        worked_tasks,
        key=lambda task: (
            -float(task.get("priority_score") or 0),
            -_priority_weight(task.get("priority")),
            -int(task.get("xp_value") or 0),
            int(task.get("estimated_minutes") or 0),
        ),
    )
    capacity = build_capacity(work_date)
    previous_capacity = build_capacity(previous_date)
    events = get_calendar_events(work_date)
    metrics = {
        "task_count": len(tasks),
        "working_today_count": len(worked_tasks),
        "completed_count": len(completed_tasks),
        "xp_earned": sum(int(task.get("xp_value") or 0) for task in completed_tasks),
        "meeting_minutes": capacity.get("meeting_minutes", 0),
        "available_focus_minutes": capacity.get("available_focus_minutes", 0),
    }
    previous_metrics = {
        "task_count": len(tasks),
        "working_today_count": len(previous_worked_tasks),
        "completed_count": len(previous_completed_tasks),
        "xp_earned": sum(int(task.get("xp_value") or 0) for task in previous_completed_tasks),
        "meeting_minutes": previous_capacity.get("meeting_minutes", 0),
        "available_focus_minutes": previous_capacity.get("available_focus_minutes", 0),
    }
    return {
        "date": work_date,
        "capacity": capacity,
        "tasks": [_task_insight(item) for item in sorted_worked],
        "completed_tasks": [_task_insight(item) for item in completed_tasks],
        "calendar_events": events,
        "metrics": metrics,
        "previous_metrics": previous_metrics,
    }


def _response(context, ai, ai_run_id):
    return {
        "date": context["date"],
        "capacity": {
            "workday_minutes": context["capacity"].get("workday_minutes", 0),
            "meeting_minutes": context["capacity"].get("meeting_minutes", 0),
            "available_focus_minutes": context["capacity"].get("available_focus_minutes", 0),
            "suggested_focus_windows": context["capacity"].get("suggested_focus_windows", []),
        },
        "task_insights": context["tasks"],
        "completed_tasks": context["completed_tasks"],
        "stat_insights": build_stat_insights(context["metrics"], context["previous_metrics"]),
        "daily_insight": ai.get("daily_insight") or "",
        "risks": ai.get("risks") or [],
        "recommendations": ai.get("recommendations") or [],
        "themes": ai.get("themes") or [],
        "generated_at": ai.get("generated_at"),
        "ai_run_id": ai_run_id,
    }


def _fallback_ai(context):
    tasks = context.get("tasks", [])
    top_task = tasks[0] if tasks else None
    available = context.get("capacity", {}).get("available_focus_minutes", 0)
    return {
        "daily_insight": (
            f"You have {available} focus minutes available. "
            f"{'Start with ' + top_task['title'] + '.' if top_task else 'Mark work for today to unlock focused recommendations.'}"
        ),
        "risks": [],
        "recommendations": [
            f"Use the next focus window for {top_task['title']}." if top_task else "Add or mark a task as Working Today."
        ],
        "themes": [],
        "generated_at": None,
    }


def _task_insight(task):
    return {
        "task_id": task["task_id"],
        "title": task["title"],
        "priority": task.get("priority"),
        "status": task.get("status"),
        "task_type": task.get("task_type"),
        "priority_score": float(task.get("priority_score") or 0),
        "effort_minutes": int(task.get("estimated_minutes") or 0),
        "xp_value": int(task.get("xp_value") or 0),
        "impact_score": float(task.get("impact") or 0),
        "insight": task.get("ai_insight") or "",
        "notes": task.get("notes") or "",
        "labels": task.get("labels") or [],
    }


def _response_task(task, work_date):
    worked_dates = _worked_dates(task.get("worked_dates"))
    return {
        **task,
        "working_today": task.get("status") != "Done" and work_date in worked_dates,
        "worked_dates": worked_dates,
    }


def _worked_dates(value):
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return sorted(str(item).strip() for item in value if str(item).strip())
    return sorted(item.strip() for item in str(value).split(",") if item.strip())


def _latest_successful_run(ai_runs, user_id, work_date):
    candidates = [
        run
        for run in ai_runs
        if run.get("user_id") == user_id
        and run.get("run_type") == RUN_TYPE
        and run.get("work_date") == work_date
        and run.get("status") == "SUCCEEDED"
    ]
    return sorted(candidates, key=lambda item: item.get("created_at") or "", reverse=True)[0] if candidates else None


def _create_ai_run(ai_runs, user_id, work_date, context, request_payload):
    now = _now_iso()
    ai_run = {
        "ai_run_id": _next_id(ai_runs, "ai_run_id"),
        "user_id": user_id,
        "run_type": RUN_TYPE,
        "work_date": work_date,
        "status": "RUNNING",
        "model_id": get_oci_genai_model_id(),
        "request_payload": {
            "system_prompt": TODAY_INSIGHT_SYSTEM_PROMPT,
            "request": request_payload,
            "context": context,
        },
        "response_payload": None,
        "error_code": None,
        "error_message": None,
        "created_at": now,
        "updated_at": now,
    }
    ai_runs.append(ai_run)
    return ai_run


def _mark_ai_run_succeeded(ai_runs, ai_run_id, response_payload):
    for run in ai_runs:
        if run.get("ai_run_id") == ai_run_id:
            run["status"] = "SUCCEEDED"
            run["response_payload"] = response_payload
            run["updated_at"] = _now_iso()
            return


def _mark_ai_run_failed(ai_runs, ai_run_id, exc):
    for run in ai_runs:
        if run.get("ai_run_id") == ai_run_id:
            run["status"] = "FAILED"
            run["error_code"] = exc.__class__.__name__
            run["error_message"] = str(exc)
            run["updated_at"] = _now_iso()
            return


def _next_id(records, id_field):
    ids = [record.get(id_field, 0) for record in records if isinstance(record.get(id_field), int)]
    return max(ids, default=9000) + 1


def _priority_weight(priority):
    return {"Critical": 10, "High": 8, "Medium": 5, "Low": 3}.get(priority, 0)


def _date_part(value):
    return str(value or "")[:10]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()
