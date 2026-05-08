from db import connection_scope


def get_user(user_id):
    with connection_scope() as conn:
        cur = conn.cursor()
        return _get_user(cur, user_id)


def get_work_items(user_id):
    with connection_scope() as conn:
        cur = conn.cursor()
        return _get_work_items(cur, user_id, _today_from_db(cur))


def get_daily_work_items(work_date, user_id):
    with connection_scope() as conn:
        cur = conn.cursor()
        return _get_daily_work_items(cur, user_id, work_date)


def get_calendar_events(work_date, user_id):
    with connection_scope() as conn:
        cur = conn.cursor()
        return _get_calendar_events(cur, user_id, work_date)


def get_dashboard_snapshot(work_date, previous_date, user_id):
    with connection_scope() as conn:
        cur = conn.cursor()
        return {
            "user": _get_user(cur, user_id),
            "tasks": _get_work_items(cur, user_id, work_date),
            "daily_work_items": _get_daily_work_items(cur, user_id, work_date),
            "previous_daily_work_items": _get_daily_work_items(cur, user_id, previous_date),
            "events": _get_calendar_events(cur, user_id, work_date),
            "previous_events": _get_calendar_events(cur, user_id, previous_date),
        }


def _get_user(cur, user_id):
    cur.execute(
        """
        SELECT
            USER_ID,
            DISPLAY_NAME,
            EMAIL,
            TIMEZONE,
            WORKDAY_START_LOCAL,
            WORKDAY_END_LOCAL,
            FOCUS_XP_MULTIPLIER
        FROM APP_USERS
        WHERE USER_ID = :user_id
        """,
        {"user_id": user_id},
    )
    row = cur.fetchone()
    if not row:
        return _default_user(user_id)
    first_name, last_name = _split_display_name(row[1])
    return {
        "user_id": row[0],
        "first_name": first_name,
        "last_name": last_name,
        "email": row[2],
        "timezone": row[3] or "Asia/Calcutta",
        "workday_start_local": row[4] or "09:00",
        "workday_end_local": row[5] or "17:00",
        "focus_xp_multiplier": float(row[6] or 1.25),
    }


def _get_work_items(cur, user_id, work_date):
    cur.execute(
        """
        SELECT
            TASK_ID,
            TITLE,
            DESCRIPTION,
            EXTERNAL_SOURCE,
            EXTERNAL_ID,
            TASK_TYPE,
            PRIORITY,
            STATUS,
            ESTIMATED_MINUTES,
            ACTUAL_MINUTES,
            XP_VALUE,
            ROW_VERSION,
            AI_DIFFICULTY,
            AI_IMPACT_SCORE,
            AI_PRIORITY_SCORE,
            AI_INSIGHT,
            TO_CHAR(COMPLETED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM')
        FROM WORK_ITEMS
        WHERE USER_ID = :user_id
        ORDER BY UPDATED_AT DESC, CREATED_AT DESC, TASK_ID DESC
        FETCH FIRST 100 ROWS ONLY
        """,
        {"user_id": user_id},
    )
    return [
        {
            "task_id": row[0],
            "title": _text(row[1]),
            "description": _text(row[2]),
            "external_source": row[3] or "Custom",
            "external_id": row[4] or "",
            "task_type": row[5] or "Task",
            "priority": row[6] or "Medium",
            "status": row[7] or "To Do",
            "estimated_minutes": row[8] or 0,
            "actual_minutes": row[9] or 0,
            "xp_value": row[10] or 0,
            "row_version": row[11] or 1,
            "ai_difficulty": row[12] or "Medium",
            "ai_impact_score": row[13] or 0,
            "ai_priority_score": row[14] or 0,
            "ai_insight": _text(row[15]),
            "completed_at": row[16],
        }
        for row in cur.fetchall()
    ]


def _get_daily_work_items(cur, user_id, work_date):
    cur.execute(
        """
        SELECT
            d.WORK_ITEM_WORK_DATE_ID,
            d.TASK_ID,
            TO_CHAR(d.WORK_DATE, 'YYYY-MM-DD'),
            d.PLANNED_MINUTES,
            d.ACTUAL_MINUTES,
            d.NOTES,
            ROW_NUMBER() OVER (
                ORDER BY NVL(w.AI_PRIORITY_SCORE, 0) DESC,
                         NVL(w.XP_VALUE, 0) DESC,
                         d.CREATED_AT,
                         w.TITLE
            ) AS RANK_ORDER
        FROM WORK_ITEM_WORK_DATES d
        JOIN WORK_ITEMS w
          ON w.TASK_ID = d.TASK_ID
         AND w.USER_ID = d.USER_ID
        WHERE d.USER_ID = :user_id
          AND d.WORK_DATE = TO_DATE(:work_date, 'YYYY-MM-DD')
        ORDER BY RANK_ORDER
        """,
        {"user_id": user_id, "work_date": work_date},
    )
    return [
        {
            "daily_work_id": row[0],
            "daily_work_item_id": row[0],
            "task_id": row[1],
            "work_date": row[2],
            "is_working_today": True,
            "planned_minutes": row[3],
            "actual_minutes": row[4],
            "notes": _text(row[5]),
            "rank_order": row[6],
        }
        for row in cur.fetchall()
    ]


def _get_calendar_events(cur, user_id, work_date):
    cur.execute(
        """
        SELECT
            EVENT_ID,
            TITLE,
            TO_CHAR(START_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM') AS START_AT,
            TO_CHAR(END_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM') AS END_AT,
            DURATION_MINUTES,
            IS_MEETING,
            IS_FOCUS_BLOCK,
            ATTENDEE_COUNT,
            EXTERNAL_SOURCE
        FROM CALENDAR_EVENTS
        WHERE USER_ID = :user_id
          AND TRUNC(CAST(START_AT AS TIMESTAMP)) = TO_DATE(:work_date, 'YYYY-MM-DD')
        ORDER BY START_AT
        """,
        {"user_id": user_id, "work_date": work_date},
    )
    return [
        {
            "event_id": row[0],
            "title": row[1],
            "start_at": row[2],
            "end_at": row[3],
            "duration_minutes": row[4] or 0,
            "is_meeting": bool(row[5]),
            "is_focus_block": bool(row[6]),
            "attendee_count": row[7],
            "external_source": row[8],
        }
        for row in cur.fetchall()
    ]


def _dashboard_task(task):
    ai = task.get("ai") or {}
    return {
        "task_id": task["task_id"],
        "title": task["title"],
        "description": task.get("description") or "",
        "external_source": task.get("external_source") or "Custom",
        "external_id": task.get("external_id") or "",
        "task_type": task.get("task_type") or "Task",
        "priority": task.get("priority") or "Medium",
        "status": task.get("status") or "To Do",
        "estimated_minutes": task.get("estimated_minutes") or ai.get("effort_minutes") or 0,
        "actual_minutes": task.get("actual_minutes") or 0,
        "xp_value": task.get("xp_value") or 0,
        "row_version": task.get("row_version") or 1,
        "ai_difficulty": ai.get("difficulty") or "Medium",
        "ai_impact_score": ai.get("impact_score") or 0,
        "ai_priority_score": ai.get("priority_score") or 0,
        "ai_insight": ai.get("insight") or "",
        "completed_at": task.get("completed_at"),
    }


def _today_from_db(cur):
    cur.execute("SELECT TO_CHAR(SYSDATE, 'YYYY-MM-DD') FROM DUAL")
    return cur.fetchone()[0]


def _default_user(user_id):
    return {
        "user_id": user_id,
        "first_name": "Gamified Tasks Dashboard",
        "last_name": "User",
        "email": "",
        "timezone": "Asia/Calcutta",
        "workday_start_local": "09:00",
        "workday_end_local": "17:00",
        "focus_xp_multiplier": 1.25,
    }


def _split_display_name(value):
    parts = str(value or "Gamified Tasks Dashboard User").strip().split()
    if not parts:
        return "Gamified Tasks Dashboard", "User"
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _text(value):
    if value is None:
        return ""
    if hasattr(value, "read"):
        return value.read()
    return str(value)
