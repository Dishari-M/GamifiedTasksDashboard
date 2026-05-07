import json

from repositories import overview_repository


def build_context(cur, user_id, work_date):
    today_tasks = _task_rows(
        cur,
        """
        SELECT
            w.TASK_ID,
            w.EXTERNAL_ID,
            w.TITLE,
            w.DESCRIPTION,
            w.EXTERNAL_SOURCE,
            w.TASK_TYPE,
            w.PRIORITY,
            w.STATUS,
            w.ESTIMATED_MINUTES,
            NVL(d.ACTUAL_MINUTES, w.ACTUAL_MINUTES) AS ACTUAL_MINUTES,
            w.XP_VALUE,
            NVL(d.NOTES, w.NOTES) AS NOTES,
            w.LABELS_JSON,
            w.AI_INSIGHT,
            w.AI_PRIORITY_SCORE,
            w.COMPLETED_AT
        FROM WORK_ITEM_WORK_DATES d
        JOIN WORK_ITEMS w
          ON w.TASK_ID = d.TASK_ID
         AND w.USER_ID = d.USER_ID
        WHERE d.USER_ID = :user_id
          AND d.WORK_DATE = TO_DATE(:work_date, 'YYYY-MM-DD')
          AND w.STATUS <> 'Done'
        ORDER BY NVL(w.AI_PRIORITY_SCORE, 0) DESC, NVL(w.XP_VALUE, 0) DESC, w.TITLE
        """,
        {"user_id": user_id, "work_date": work_date},
    )
    completed = _task_rows(
        cur,
        """
        SELECT
            TASK_ID,
            EXTERNAL_ID,
            TITLE,
            DESCRIPTION,
            EXTERNAL_SOURCE,
            TASK_TYPE,
            PRIORITY,
            STATUS,
            ESTIMATED_MINUTES,
            ACTUAL_MINUTES,
            XP_VALUE,
            NOTES,
            LABELS_JSON,
            AI_INSIGHT,
            AI_PRIORITY_SCORE,
            COMPLETED_AT
        FROM WORK_ITEMS
        WHERE USER_ID = :user_id
          AND STATUS = 'Done'
          AND COMPLETED_AT >= CAST(TO_DATE(:work_date, 'YYYY-MM-DD') AS TIMESTAMP)
          AND COMPLETED_AT < CAST(TO_DATE(:work_date, 'YYYY-MM-DD') + 1 AS TIMESTAMP)
        ORDER BY COMPLETED_AT
        """,
        {"user_id": user_id, "work_date": work_date},
    )
    blockers = _task_rows(
        cur,
        """
        SELECT
            TASK_ID,
            EXTERNAL_ID,
            TITLE,
            DESCRIPTION,
            EXTERNAL_SOURCE,
            TASK_TYPE,
            PRIORITY,
            STATUS,
            ESTIMATED_MINUTES,
            ACTUAL_MINUTES,
            XP_VALUE,
            NOTES,
            LABELS_JSON,
            AI_INSIGHT,
            AI_PRIORITY_SCORE,
            COMPLETED_AT
        FROM WORK_ITEMS
        WHERE USER_ID = :user_id
          AND STATUS = 'Blocked'
          AND (
            EXISTS (
                SELECT 1 FROM WORK_ITEM_WORK_DATES d
                WHERE d.USER_ID = WORK_ITEMS.USER_ID
                  AND d.TASK_ID = WORK_ITEMS.TASK_ID
                  AND d.WORK_DATE = TO_DATE(:work_date, 'YYYY-MM-DD')
            )
            OR NOT EXISTS (
                SELECT 1 FROM WORK_ITEM_WORK_DATES d
                WHERE d.USER_ID = WORK_ITEMS.USER_ID
                  AND d.WORK_DATE = TO_DATE(:work_date, 'YYYY-MM-DD')
            )
          )
        ORDER BY NVL(AI_PRIORITY_SCORE, 0) DESC, TITLE
        """,
        {"user_id": user_id, "work_date": work_date},
    )
    focus_sessions = overview_repository.fetch_focus_sessions(cur, user_id, work_date, work_date)
    calendar_events = overview_repository.fetch_calendar_events(cur, user_id, work_date, work_date)
    meetings = [event for event in calendar_events if event.get("is_meeting")]
    daily_overviews = overview_repository.fetch_daily_overviews(cur, user_id, work_date, work_date)
    today_notes = _notes_from_tasks(today_tasks + completed + blockers)
    return {
        "date": work_date,
        "metrics": {
            "today_task_count": len(today_tasks),
            "completed_count": len(completed),
            "blocker_count": len(blockers),
            "planned_minutes": sum(task["estimated_minutes"] for task in today_tasks),
            "focus_session_count": len(focus_sessions),
            "focus_minutes": sum(session.get("actual_minutes") or 0 for session in focus_sessions),
            "meeting_count": len(meetings),
            "meeting_minutes": sum(event.get("duration_minutes") or 0 for event in meetings),
            "daily_overview_count": len(daily_overviews),
            "note_count": len(today_notes),
        },
        "today_work_items": today_tasks,
        "completed_today": completed,
        "blockers": blockers,
        "today_notes": today_notes,
        "focus_sessions": focus_sessions,
        "calendar_events": calendar_events,
        "meetings": meetings,
        "daily_overviews": daily_overviews,
    }


def _task_rows(cur, sql, binds):
    cur.execute(sql, binds)
    return [
        {
            "task_id": row[0],
            "external_id": row[1] or "",
            "title": _text(row[2]),
            "description": _text(row[3]),
            "source": row[4] or "Custom",
            "task_type": row[5] or "Task",
            "priority": row[6] or "Medium",
            "status": row[7] or "To Do",
            "estimated_minutes": row[8] or 0,
            "actual_minutes": row[9] or 0,
            "xp_value": row[10] or 0,
            "notes": _text(row[11]),
            "labels": _json_list(row[12]),
            "ai_insight": _text(row[13]),
            "priority_score": float(row[14] or 0),
            "completed_at": row[15].isoformat() if row[15] else None,
        }
        for row in cur.fetchall()
    ]


def _json_list(value):
    text = _text(value)
    if not text:
        return []
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []


def _notes_from_tasks(tasks):
    notes = []
    for task in tasks:
        note = _text(task.get("notes")).strip()
        if note and note not in notes:
            notes.append(note)
    return notes


def _text(value):
    if value is None:
        return ""
    if hasattr(value, "read"):
        return value.read()
    return str(value)
