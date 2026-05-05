from datetime import date as date_type
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException

try:
    import oracledb
except ImportError:
    oracledb = None

from config import get_data_mode, get_oci_genai_model_id
from repositories import overview_repository
from services import phase8_mock_data
from services.overview_ai_service import (
    DAILY_OVERVIEW_SYSTEM_PROMPT,
    WEEKLY_OVERVIEW_SYSTEM_PROMPT,
    build_daily_ai_output,
    build_weekly_ai_output,
)
from services.phase8_data_provider import (
    get_calendar_events,
    get_daily_work_items,
    get_work_items,
    resolve_work_date,
)


DEFAULT_USER_ID = 1


def daily_overview_response(date=None):
    work_date = resolve_work_date(date)
    return {"data": get_daily_overview(work_date), "meta": {"request_id": str(uuid4())}}


def weekly_overview_response(week_start=None):
    start = _week_start(week_start)
    return {"data": get_weekly_overview(start), "meta": {"request_id": str(uuid4())}}


def generate_daily_overview_response(payload):
    work_date = resolve_work_date(payload.date)
    return {"data": generate_daily_overview(work_date, payload), "meta": {"request_id": str(uuid4())}}


def save_daily_overview_response(payload):
    work_date = resolve_work_date(payload.date)
    return {"data": save_daily_overview(work_date, payload), "meta": {"request_id": str(uuid4())}}


def generate_weekly_overview_response(payload):
    week_start = _week_start(payload.week_start)
    return {"data": generate_weekly_overview(week_start, payload), "meta": {"request_id": str(uuid4())}}


def get_daily_overview(work_date):
    if get_data_mode() == "oracle":
        return _oracle_daily_overview(work_date, generate=False)
    context = _mock_daily_context(work_date)
    ai = build_daily_ai_output(context)
    return _daily_response(context, ai)


def generate_daily_overview(work_date, payload):
    if get_data_mode() == "oracle":
        return _oracle_daily_overview(work_date, generate=True, request_payload=payload.model_dump())
    context = _mock_daily_context(work_date)
    ai = build_daily_ai_output(context)
    return {**_daily_response(context, ai), "daily_overview_id": 8101, "ai_run_id": 9005}


def save_daily_overview(work_date, payload):
    if get_data_mode() == "oracle":
        return _oracle_save_daily_overview(work_date, payload)
    context = _mock_daily_context(work_date)
    overview = _daily_response(context, _manual_daily_ai_payload(payload))
    return {**_apply_daily_overrides(overview, payload), "daily_overview_id": 8101, "ai_run_id": None}


def get_weekly_overview(week_start):
    week_end = _add_days(week_start, 6)
    if get_data_mode() == "oracle":
        return _oracle_weekly_overview(week_start, week_end, generate=False)
    context = _mock_weekly_context(week_start, week_end)
    ai = build_weekly_ai_output(context)
    return _weekly_response(context, ai)


def generate_weekly_overview(week_start, payload):
    week_end = _add_days(week_start, 6)
    if get_data_mode() == "oracle":
        return _oracle_weekly_overview(week_start, week_end, generate=True, request_payload=payload.model_dump())
    context = _mock_weekly_context(week_start, week_end)
    ai = build_weekly_ai_output(context)
    return {**_weekly_response(context, ai), "weekly_overview_id": 8201, "ai_run_id": 9006}


def _mock_daily_context(work_date):
    tasks = get_work_items()
    daily_work = get_daily_work_items(work_date)
    calendar_events = get_calendar_events(work_date)
    focus_sessions = phase8_mock_data.get_mock_focus_sessions(work_date, work_date)
    completed = [task for task in tasks if _completed_between(task, work_date, work_date)]
    worked_ids = {item["task_id"] for item in daily_work if item.get("is_working_today")}
    worked = [
        {
            **task,
            "work_date": work_date,
            "planned_minutes": next((item.get("planned_minutes") for item in daily_work if item["task_id"] == task["task_id"]), None),
        }
        for task in tasks
        if task["task_id"] in worked_ids
    ]
    return _context(
        start_date=work_date,
        end_date=work_date,
        completed_tasks=completed,
        worked_tasks=worked,
        calendar_events=calendar_events,
        focus_sessions=focus_sessions,
        daily_overviews=[],
    )


def _mock_weekly_context(week_start, week_end):
    tasks = get_work_items()
    completed = [task for task in tasks if _completed_between(task, week_start, week_end)]
    worked = []
    events = []
    focus_sessions = phase8_mock_data.get_mock_focus_sessions(week_start, week_end)
    for day in _date_range(week_start, week_end):
        daily_work = get_daily_work_items(day)
        events.extend(get_calendar_events(day))
        worked_ids = {item["task_id"] for item in daily_work if item.get("is_working_today")}
        worked.extend([{**task, "work_date": day} for task in tasks if task["task_id"] in worked_ids])
    return _context(
        start_date=week_start,
        end_date=week_end,
        completed_tasks=completed,
        worked_tasks=worked,
        calendar_events=events,
        focus_sessions=focus_sessions,
        daily_overviews=[],
    )


def _oracle_daily_overview(work_date, generate=False, request_payload=None):
    conn = None
    ai_run_id = None
    try:
        conn = _get_connection()
        cur = conn.cursor()
        saved = overview_repository.fetch_daily_overview_row(cur, DEFAULT_USER_ID, work_date)
        context = _oracle_context(cur, work_date, work_date)
        if saved and not generate:
            return {**_daily_response(context, saved), "daily_overview_id": saved["daily_overview_id"], "ai_run_id": saved["source_ai_run_id"]}

        request = _ai_request_payload("DAILY_OVERVIEW", DAILY_OVERVIEW_SYSTEM_PROMPT, context, request_payload)
        ai_run_id = overview_repository.insert_ai_run(
            cur,
            DEFAULT_USER_ID,
            "DAILY_OVERVIEW",
            get_oci_genai_model_id(),
            request,
        )
        conn.commit()
        ai = build_daily_ai_output(context)
        cur = conn.cursor()
        overview = _daily_response(context, ai)
        overview_repository.upsert_daily_overview(cur, DEFAULT_USER_ID, work_date, ai_run_id, overview)
        overview_repository.update_ai_run(cur, ai_run_id, "SUCCEEDED", ai)
        conn.commit()
        return {**overview, "ai_run_id": ai_run_id}
    except HTTPException:
        if conn:
            conn.rollback()
        if ai_run_id:
            _mark_ai_failed(ai_run_id, "FAILED", "AI_PROVIDER_ERROR", "Overview AI generation failed.")
        raise
    except _oracle_database_error() as exc:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=503, detail="Overview storage is unavailable.") from exc
    finally:
        if conn:
            conn.close()


def _oracle_weekly_overview(week_start, week_end, generate=False, request_payload=None):
    conn = None
    ai_run_id = None
    try:
        conn = _get_connection()
        cur = conn.cursor()
        saved = overview_repository.fetch_weekly_overview_row(cur, DEFAULT_USER_ID, week_start)
        context = _oracle_context(cur, week_start, week_end)
        context["daily_overviews"] = overview_repository.fetch_daily_overviews_for_week(cur, DEFAULT_USER_ID, week_start, week_end)
        if saved and not generate:
            return {**_weekly_response(context, saved), "weekly_overview_id": saved["weekly_overview_id"], "ai_run_id": saved["source_ai_run_id"]}

        request = _ai_request_payload("WEEKLY_OVERVIEW", WEEKLY_OVERVIEW_SYSTEM_PROMPT, context, request_payload)
        ai_run_id = overview_repository.insert_ai_run(
            cur,
            DEFAULT_USER_ID,
            "WEEKLY_OVERVIEW",
            get_oci_genai_model_id(),
            request,
        )
        conn.commit()
        ai = build_weekly_ai_output(context)
        cur = conn.cursor()
        overview = _weekly_response(context, ai)
        overview_repository.upsert_weekly_overview(cur, DEFAULT_USER_ID, week_start, week_end, ai_run_id, overview)
        overview_repository.update_ai_run(cur, ai_run_id, "SUCCEEDED", ai)
        conn.commit()
        return {**overview, "ai_run_id": ai_run_id}
    except HTTPException:
        if conn:
            conn.rollback()
        if ai_run_id:
            _mark_ai_failed(ai_run_id, "FAILED", "AI_PROVIDER_ERROR", "Weekly overview AI generation failed.")
        raise
    except _oracle_database_error() as exc:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=503, detail="Overview storage is unavailable.") from exc
    finally:
        if conn:
            conn.close()


def _oracle_save_daily_overview(work_date, payload):
    conn = None
    try:
        conn = _get_connection()
        cur = conn.cursor()
        saved = overview_repository.fetch_daily_overview_row(cur, DEFAULT_USER_ID, work_date)
        context = _oracle_context(cur, work_date, work_date)
        overview = _daily_response(context, _manual_daily_ai_payload(payload, saved))
        overview = _apply_daily_overrides(overview, payload)
        overview_repository.upsert_daily_overview(cur, DEFAULT_USER_ID, work_date, saved.get("source_ai_run_id"), overview)
        conn.commit()
        cur = conn.cursor()
        refreshed = overview_repository.fetch_daily_overview_row(cur, DEFAULT_USER_ID, work_date) or {}
        return {
            **overview,
            "daily_overview_id": refreshed.get("daily_overview_id"),
            "ai_run_id": refreshed.get("source_ai_run_id"),
        }
    except _oracle_database_error() as exc:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=503, detail="Daily overview storage is unavailable.") from exc
    finally:
        if conn:
            conn.close()


def _oracle_context(cur, start_date, end_date):
    completed = overview_repository.fetch_completed_tasks(cur, DEFAULT_USER_ID, start_date, end_date)
    worked = overview_repository.fetch_worked_tasks(cur, DEFAULT_USER_ID, start_date, end_date)
    events = overview_repository.fetch_calendar_events(cur, DEFAULT_USER_ID, start_date, end_date)
    focus_sessions = overview_repository.fetch_focus_sessions(cur, DEFAULT_USER_ID, start_date, end_date)
    return _context(start_date, end_date, completed, worked, events, focus_sessions, [])


def _context(start_date, end_date, completed_tasks, worked_tasks, calendar_events, focus_sessions, daily_overviews):
    completed = [_normalize_task(task) for task in completed_tasks]
    worked = [_normalize_task(task) for task in worked_tasks]
    events = [_normalize_event(event) for event in calendar_events]
    focus = [_normalize_focus(session) for session in focus_sessions]
    meeting_events = [event for event in events if event["is_meeting"]]
    focus_minutes = sum(item["actual_minutes"] for item in focus)
    meeting_minutes = sum(event["duration_minutes"] for event in meeting_events)
    return {
        "start_date": start_date,
        "end_date": end_date,
        "metrics": {
            "tasks_completed": len(completed),
            "xp_earned": sum(task["xp_value"] for task in completed),
            "meeting_minutes": meeting_minutes,
            "meeting_count": len(meeting_events),
            "focus_minutes": focus_minutes,
            "focus_session_count": len(focus),
            "worked_task_count": len(worked),
        },
        "completed_tasks": completed,
        "worked_tasks": worked,
        "calendar_events": events,
        "focus_sessions": focus,
        "daily_overviews": daily_overviews,
    }


def _daily_response(context, ai):
    metrics = context["metrics"]
    return {
        "date": context["start_date"],
        "tasks_completed": metrics["tasks_completed"],
        "xp_earned": metrics["xp_earned"],
        "meeting_minutes": metrics["meeting_minutes"],
        "focus_minutes": metrics["focus_minutes"],
        "accomplished_tasks": context["completed_tasks"],
        "worked_tasks": context["worked_tasks"],
        "focus_sessions": context["focus_sessions"],
        "meeting_summary": {
            "meeting_count": metrics["meeting_count"],
            "meeting_minutes": metrics["meeting_minutes"],
        },
        "new_learnings": ai.get("new_learnings", []),
        "went_well": ai.get("went_well", []),
        "went_wrong": ai.get("went_wrong", []),
        "themes": ai.get("themes", []),
        "summary": ai.get("summary", ""),
        "generated_at": ai.get("generated_at"),
    }


def _weekly_response(context, ai):
    metrics = context["metrics"]
    return {
        "week_start": context["start_date"],
        "week_end": context["end_date"],
        "tasks_completed": metrics["tasks_completed"],
        "xp_earned": metrics["xp_earned"],
        "meeting_minutes": metrics["meeting_minutes"],
        "focus_minutes": metrics["focus_minutes"],
        "top_accomplishments": ai.get("top_accomplishments", []),
        "new_learnings": ai.get("new_learnings", []),
        "themes": ai.get("themes", []),
        "went_well": ai.get("went_well", []),
        "went_wrong": ai.get("went_wrong", []),
        "summary": ai.get("summary", ""),
        "completed_tasks": context["completed_tasks"],
        "daily_overviews": context.get("daily_overviews", []),
        "generated_at": ai.get("generated_at"),
    }


def _manual_daily_ai_payload(payload, saved=None):
    saved = saved or {}
    return {
        "new_learnings": payload.new_learnings,
        "went_well": payload.went_well,
        "went_wrong": payload.went_wrong,
        "themes": saved.get("themes", []),
        "summary": payload.summary or saved.get("summary") or "",
        "generated_at": saved.get("updated_at"),
    }


def _apply_daily_overrides(overview, payload):
    if payload.meeting_minutes is not None:
        overview["meeting_minutes"] = payload.meeting_minutes
        overview["meeting_summary"] = {
            **overview.get("meeting_summary", {}),
            "meeting_minutes": payload.meeting_minutes,
        }
    if payload.focus_minutes is not None:
        overview["focus_minutes"] = payload.focus_minutes
    return overview


def _normalize_task(task):
    return {
        "task_id": task.get("task_id"),
        "title": task.get("title", ""),
        "description": task.get("description", ""),
        "task_type": task.get("task_type", "Task"),
        "priority": task.get("priority", "Medium"),
        "status": task.get("status", "To Do"),
        "estimated_minutes": task.get("estimated_minutes") or 0,
        "actual_minutes": task.get("actual_minutes") or 0,
        "xp_value": task.get("xp_value") or 0,
        "notes": task.get("notes") or "",
        "labels": task.get("labels") or [],
        "ai_category": task.get("ai_category"),
        "ai_insight": task.get("ai_insight") or task.get("ai", {}).get("insight", ""),
        "completed_at": task.get("completed_at"),
        "work_date": task.get("work_date"),
        "planned_minutes": task.get("planned_minutes"),
    }


def _normalize_event(event):
    return {
        "event_id": event.get("event_id"),
        "title": event.get("title", ""),
        "start_at": event.get("start_at"),
        "end_at": event.get("end_at"),
        "duration_minutes": event.get("duration_minutes") or 0,
        "is_meeting": bool(event.get("is_meeting")),
        "is_focus_block": bool(event.get("is_focus_block")),
        "external_source": event.get("external_source"),
    }


def _normalize_focus(session):
    return {
        "focus_session_id": session.get("focus_session_id"),
        "task_id": session.get("task_id"),
        "task_title": session.get("task_title") or session.get("title") or "Focus session",
        "session_date": session.get("session_date") or session.get("work_date"),
        "started_at": session.get("started_at"),
        "ended_at": session.get("ended_at"),
        "planned_minutes": session.get("planned_minutes") or 0,
        "actual_minutes": session.get("actual_minutes") or session.get("duration_minutes") or 0,
        "status": session.get("status") or session.get("outcome_type") or "Completed",
        "xp_awarded": session.get("xp_awarded") or 0,
        "notes": session.get("notes") or session.get("outcome_note") or "",
    }


def _completed_between(task, start_date, end_date):
    completed_at = task.get("completed_at")
    if not completed_at:
        return False
    day = completed_at[:10]
    return start_date <= day <= end_date


def _week_start(value=None):
    if value:
        parsed = _parse_date(value)
    else:
        parsed = date_type.today()
    return (parsed - timedelta(days=parsed.weekday())).isoformat()


def _add_days(value, days):
    return (_parse_date(value) + timedelta(days=days)).isoformat()


def _date_range(start_date, end_date):
    current = _parse_date(start_date)
    end = _parse_date(end_date)
    while current <= end:
        yield current.isoformat()
        current += timedelta(days=1)


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Date must use YYYY-MM-DD format.") from exc


def _ai_request_payload(run_type, system_prompt, context, request_payload):
    return {
        "run_type": run_type,
        "model_id": get_oci_genai_model_id(),
        "system_prompt": system_prompt,
        "request": request_payload or {},
        "context": context,
    }


def _mark_ai_failed(ai_run_id, status, error_code, error_message):
    conn = None
    try:
        conn = _get_connection()
        cur = conn.cursor()
        overview_repository.update_ai_run(cur, ai_run_id, status, None, error_code, error_message)
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


def _oracle_database_error():
    if oracledb is None:
        return Exception
    return oracledb.DatabaseError


def _get_connection():
    try:
        from db import get_connection
    except ImportError as exc:
        raise HTTPException(
            status_code=501,
            detail="DEVQUEST_DATA_MODE=oracle requires the oracledb package and Oracle connection settings.",
        ) from exc
    return get_connection()
