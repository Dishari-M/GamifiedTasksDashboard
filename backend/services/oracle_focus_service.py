from __future__ import annotations

from datetime import UTC, datetime

import oracledb
from fastapi import HTTPException

from db import get_connection
from repositories import focus_repository


VALID_OUTCOMES = {"Progress made", "Blocked", "Ready for review", "Completed"}


def list_oracle_focus_sessions(filters=None, user_id=1):
    filters = dict(filters or {})
    date_from = _normalize_date(filters.get("date_from") or filters.get("date") or filters.get("work_date")) if (
        filters.get("date_from") or filters.get("date") or filters.get("work_date")
    ) else None
    date_to = _normalize_date(filters.get("date_to") or filters.get("date") or filters.get("work_date")) if (
        filters.get("date_to") or filters.get("date") or filters.get("work_date")
    ) else None
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        return focus_repository.list_focus_sessions(cur, int(user_id), date_from, date_to)
    except oracledb.DatabaseError as exc:
        raise HTTPException(status_code=503, detail="Focus session storage is unavailable.") from exc
    finally:
        if conn:
            conn.close()


def create_oracle_focus_session(payload, user_id=1):
    data = _normalize_payload(payload)
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        quest_item_id = focus_repository.resolve_quest_item_id(cur, int(user_id), data.get("quest_id"))
        base_xp = focus_repository.fetch_task_xp(cur, int(user_id), data.get("task_id"))
        xp_multiplier = focus_repository.fetch_focus_multiplier(cur, int(user_id)) if data["duration_minutes"] > 0 else 1.0
        xp_awarded = round(base_xp * xp_multiplier) if base_xp else 0
        focus_session_id = focus_repository.insert_focus_session(cur, int(user_id), data, quest_item_id, xp_multiplier, xp_awarded)
        focus_repository.sync_quest_focus(cur, quest_item_id, data["duration_minutes"], xp_multiplier, xp_awarded)
        conn.commit()
        return focus_repository.fetch_focus_session(cur, int(user_id), focus_session_id)
    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except oracledb.DatabaseError as exc:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=503, detail="Focus session storage is unavailable.") from exc
    finally:
        if conn:
            conn.close()


def _normalize_payload(payload):
    data = dict(payload or {})
    duration_seconds = _required_int(data.get("duration_seconds"), "duration_seconds")
    duration_minutes = _required_int(data.get("duration_minutes"), "duration_minutes")
    outcome_type = str(data.get("outcome_type") or "").strip() or "Progress made"
    if outcome_type not in VALID_OUTCOMES:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "Invalid outcome_type.", "details": {"field": "outcome_type"}})
    started_at = _parse_datetime(data.get("started_at"), "started_at")
    ended_at = _parse_datetime(data.get("ended_at"), "ended_at")
    work_date = str(data.get("work_date") or data.get("session_date") or started_at.date().isoformat()).strip()
    _normalize_date(work_date)
    return {
        "client_focus_session_id": data.get("focus_session_id") or data.get("client_focus_session_id"),
        "task_id": str(data.get("task_id") or "").strip() or None,
        "quest_id": str(data.get("quest_id") or "").strip() or None,
        "session_date": work_date,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_seconds": duration_seconds,
        "duration_minutes": max(1, duration_minutes),
        "outcome_type": outcome_type,
        "outcome_note": str(data.get("outcome_note") or "").strip(),
        "status": "COMPLETED",
    }


def _required_int(value, field):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": f"{field} must be an integer.", "details": {"field": field}})
    if parsed < 0:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": f"{field} cannot be negative.", "details": {"field": field}})
    return parsed


def _parse_datetime(value, field):
    text = str(value or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": f"{field} is required.", "details": {"field": field}})
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": f"{field} must use ISO datetime format.", "details": {"field": field}}) from exc


def _normalize_date(value):
    text = str(value or "").strip()
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "Date must use YYYY-MM-DD format.", "details": {"field": "date"}}) from exc
    return text
