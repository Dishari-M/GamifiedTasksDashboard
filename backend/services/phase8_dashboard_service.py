from uuid import uuid4

from config import get_data_mode
from repositories import phase8_oracle_repository
from services.api_cache import canonical_cache_key, get_cached_response, get_default_cache_ttl_seconds, invalidate_namespace, set_cached_response
from services.phase8_ai_insight_service import build_ai_insight
from services.phase8_capacity_service import build_capacity
from services.phase8_data_provider import (
    get_calendar_events,
    get_daily_work_items,
    get_focus_sessions,
    get_work_items,
    resolve_work_date,
)
from services.stat_insight_service import build_stat_insights, previous_date_key


DASHBOARD_CACHE_TTL_SECONDS = get_default_cache_ttl_seconds
DASHBOARD_CACHE_NAMESPACE = "dashboard_today"


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


def _focus_window_response(window):
    return {
        "event_id": f"focus-{window['start_at']}",
        "title": "Focus Time Block",
        "start_at": window["start_at"],
        "end_at": window["end_at"],
        "duration_minutes": window["duration_minutes"],
        "is_meeting": False,
        "is_focus_block": True,
        "external_source": "Capacity",
    }


def _completed_on_date(task, work_date):
    completed_at = task.get("completed_at")
    return bool(completed_at and completed_at.startswith(work_date))


def build_dashboard(date=None, user_id=None):
    work_date = resolve_work_date(date)
    previous_date = previous_date_key(work_date)
    if get_data_mode() == "oracle":
        snapshot = phase8_oracle_repository.get_dashboard_snapshot(work_date, previous_date, user_id)
        tasks = snapshot["tasks"]
        daily_work_items = [item for item in snapshot["daily_work_items"] if item["is_working_today"]]
        previous_daily_work_items = [item for item in snapshot["previous_daily_work_items"] if item["is_working_today"]]
        events = snapshot["events"]
        focus_sessions = snapshot["focus_sessions"]
        previous_focus_sessions = snapshot["previous_focus_sessions"]
        capacity = build_capacity(work_date, user=snapshot["user"], events=events)
        previous_capacity = build_capacity(previous_date, user=snapshot["user"], events=snapshot["previous_events"])
    else:
        tasks = get_work_items(user_id)
        daily_work_items = [item for item in get_daily_work_items(work_date, user_id) if item["is_working_today"]]
        previous_daily_work_items = [item for item in get_daily_work_items(previous_date, user_id) if item["is_working_today"]]
        events = get_calendar_events(work_date, user_id)
        focus_sessions = get_focus_sessions(work_date, user_id)
        previous_focus_sessions = get_focus_sessions(previous_date, user_id)
        capacity = build_capacity(work_date, user_id=user_id)
        previous_capacity = build_capacity(previous_date, user_id=user_id)

    task_by_id = {task["task_id"]: task for task in tasks}
    daily_by_task_id = {item["task_id"]: item for item in daily_work_items}
    planned_tasks = [
        task_by_id[item["task_id"]]
        for item in daily_work_items
        if item["task_id"] in task_by_id and task_by_id[item["task_id"]].get("status") != "Done"
    ]

    top_mission_rows = sorted(
        [item for item in daily_work_items if task_by_id.get(item["task_id"], {}).get("status") != "Done"],
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
        if task.get("status") != "Done"
    ]

    tasks_completed_today = sum(1 for task in tasks if _completed_on_date(task, work_date))
    previous_tasks_completed = sum(1 for task in tasks if _completed_on_date(task, previous_date))
    total_xp = sum(task["xp_value"] for task in tasks if task["status"] == "Done")
    previous_xp = sum(task["xp_value"] for task in tasks if _completed_on_date(task, previous_date))
    focus_minutes = sum(int(session.get("actual_minutes") or session.get("duration_minutes") or 0) for session in focus_sessions)
    previous_focus_minutes = sum(int(session.get("actual_minutes") or session.get("duration_minutes") or 0) for session in previous_focus_sessions)
    schedule = [_schedule_response(event) for event in events]
    if not any(event.get("is_focus_block") for event in events):
        schedule.extend(_focus_window_response(window) for window in capacity["suggested_focus_windows"])
        schedule.sort(key=lambda item: item["start_at"])
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


def dashboard_today_response(date=None, user_id=None):
    work_date = resolve_work_date(date)
    cache_key = canonical_cache_key({"mode": get_data_mode(), "user_id": user_id, "date": work_date})
    cached = get_cached_response(DASHBOARD_CACHE_NAMESPACE, cache_key, DASHBOARD_CACHE_TTL_SECONDS())
    if cached:
        return {
            "data": cached,
            "meta": {"request_id": str(uuid4()), "cache": "hit"},
        }
    data = build_dashboard(work_date, user_id)
    set_cached_response(DASHBOARD_CACHE_NAMESPACE, cache_key, data, user_id=user_id)
    return {
        "data": data,
        "meta": {"request_id": str(uuid4()), "cache": "miss"},
    }


def invalidate_dashboard_cache(user_id=None):
    invalidate_namespace(DASHBOARD_CACHE_NAMESPACE, user_id=user_id)
