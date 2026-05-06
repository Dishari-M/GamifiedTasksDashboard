from uuid import uuid4
from datetime import datetime, timezone

from config import get_data_mode
from repositories import phase8_oracle_repository
from services.phase8_ai_insight_service import build_ai_insight
from services.phase8_capacity_service import build_capacity
from services.phase8_data_provider import (
    get_calendar_events,
    get_daily_work_items,
    get_work_items,
    resolve_work_date,
)
from services.stat_insight_service import build_stat_insights, previous_date_key


DASHBOARD_CACHE_TTL_SECONDS = 15
_DASHBOARD_CACHE = {}


def _task_response(task, working_today=False, rank_order=None, planned_minutes=None):
    return {
        "task_id": task["task_id"],
        "title": task["title"],
        "description": task["description"],
        "external_source": task["external_source"],
        "external_id": task["external_id"],
        "task_type": task["task_type"],
        "priority": task["priority"],
        "status": task["status"],
        "estimated_minutes": task["estimated_minutes"],
        "actual_minutes": task["actual_minutes"],
        "xp_value": task["xp_value"],
        "working_today": working_today,
        "row_version": task.get("row_version", 1),
        "rank_order": rank_order,
        "planned_minutes": planned_minutes,
        "ai": {
            "difficulty": task["ai_difficulty"],
            "impact_score": task["ai_impact_score"],
            "priority_score": task["ai_priority_score"],
            "insight": task["ai_insight"],
        },
        "completed_at": task["completed_at"],
    }


def _top_mission_response(task, daily_work):
    return {
        "task_id": task["task_id"],
        "title": task["title"],
        "priority": task["priority"],
        "rank_order": daily_work["rank_order"],
        "estimated_minutes": task["estimated_minutes"],
        "xp_value": task["xp_value"],
        "ai_reason": task["ai_insight"],
    }


def _schedule_response(event):
    return {
        "event_id": event["event_id"],
        "title": event["title"],
        "start_at": event["start_at"],
        "end_at": event["end_at"],
        "duration_minutes": event["duration_minutes"],
        "is_meeting": event["is_meeting"],
        "is_focus_block": event["is_focus_block"],
        "external_source": event["external_source"],
    }


def _completed_on_date(task, work_date):
    completed_at = task.get("completed_at")
    return bool(completed_at and completed_at.startswith(work_date))


def build_dashboard(date=None):
    work_date = resolve_work_date(date)
    previous_date = previous_date_key(work_date)
    if get_data_mode() == "oracle":
        snapshot = phase8_oracle_repository.get_dashboard_snapshot(work_date, previous_date)
        tasks = snapshot["tasks"]
        daily_work_items = [item for item in snapshot["daily_work_items"] if item["is_working_today"]]
        previous_daily_work_items = [item for item in snapshot["previous_daily_work_items"] if item["is_working_today"]]
        events = snapshot["events"]
        capacity = build_capacity(work_date, user=snapshot["user"], events=events)
        previous_capacity = build_capacity(previous_date, user=snapshot["user"], events=snapshot["previous_events"])
    else:
        tasks = get_work_items()
        daily_work_items = [item for item in get_daily_work_items(work_date) if item["is_working_today"]]
        previous_daily_work_items = [item for item in get_daily_work_items(previous_date) if item["is_working_today"]]
        events = get_calendar_events(work_date)
        capacity = build_capacity(work_date)
        previous_capacity = build_capacity(previous_date)

    task_by_id = {task["task_id"]: task for task in tasks}
    daily_by_task_id = {item["task_id"]: item for item in daily_work_items}
    planned_tasks = [task_by_id[item["task_id"]] for item in daily_work_items if item["task_id"] in task_by_id]

    top_mission_rows = sorted(
        daily_work_items,
        key=lambda item: (
            item["rank_order"] if item["rank_order"] is not None else 999,
            -(task_by_id.get(item["task_id"], {}).get("ai_priority_score", 0)),
            -(task_by_id.get(item["task_id"], {}).get("xp_value", 0)),
        ),
    )[:3]
    top_missions = [
        _top_mission_response(task_by_id[item["task_id"]], item)
        for item in top_mission_rows
        if item["task_id"] in task_by_id
    ]

    dashboard_tasks = [
        _task_response(
            task,
            working_today=task["task_id"] in daily_by_task_id,
            rank_order=daily_by_task_id.get(task["task_id"], {}).get("rank_order"),
            planned_minutes=daily_by_task_id.get(task["task_id"], {}).get("planned_minutes"),
        )
        for task in tasks
    ]

    tasks_completed_today = sum(1 for task in tasks if _completed_on_date(task, work_date))
    previous_tasks_completed = sum(1 for task in tasks if _completed_on_date(task, previous_date))
    total_xp = sum(task["xp_value"] for task in tasks if task["status"] == "Done")
    previous_xp = sum(task["xp_value"] for task in tasks if _completed_on_date(task, previous_date))
    focus_minutes = max(capacity["available_focus_minutes"] - 10, 0)
    previous_focus_minutes = max(previous_capacity["available_focus_minutes"] - 10, 0)
    schedule = [_schedule_response(event) for event in events]
    ai_insight = build_ai_insight(work_date, capacity, top_missions, dashboard_tasks, schedule, planned_tasks)
    stats = {
        "total_xp": total_xp,
        "tasks_completed_today": tasks_completed_today,
        "tasks_planned_today": len(daily_work_items),
        "focus_minutes": focus_minutes,
        "meeting_minutes": capacity["meeting_minutes"],
        "available_focus_minutes": capacity["available_focus_minutes"],
    }
    previous_stats = {
        "total_xp": previous_xp,
        "tasks_completed_today": previous_tasks_completed,
        "tasks_planned_today": len(previous_daily_work_items),
        "focus_minutes": previous_focus_minutes,
        "meeting_minutes": previous_capacity["meeting_minutes"],
        "available_focus_minutes": previous_capacity["available_focus_minutes"],
    }

    return {
        "date": work_date,
        "stats": stats,
        "stat_insights": build_stat_insights(stats, previous_stats),
        "top_missions": top_missions,
        "tasks": dashboard_tasks,
        "schedule": schedule,
        "ai_insight": ai_insight,
    }


def dashboard_today_response(date=None):
    work_date = resolve_work_date(date)
    cache_key = (get_data_mode(), work_date)
    cached = _DASHBOARD_CACHE.get(cache_key)
    now = datetime.now(timezone.utc).timestamp()
    if cached and now - cached["cached_at"] <= DASHBOARD_CACHE_TTL_SECONDS:
        return {
            "data": cached["data"],
            "meta": {"request_id": str(uuid4()), "cache": "hit"},
        }
    data = build_dashboard(work_date)
    _DASHBOARD_CACHE[cache_key] = {"cached_at": now, "data": data}
    return {
        "data": data,
        "meta": {"request_id": str(uuid4()), "cache": "miss"},
    }
