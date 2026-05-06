from db import get_connection
from repositories import task_repository


DEFAULT_USER_ID = 1


def get_user():
    conn = get_connection()
    try:
        cur = conn.cursor()
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
            {"user_id": DEFAULT_USER_ID},
        )
        row = cur.fetchone()
        if not row:
            return _default_user()
        first_name, last_name = _split_display_name(row[1])
        return {
            "user_id": row[0],
            "first_name": first_name,
            "last_name": last_name,
            "email": row[2],
            "timezone": row[3] or "Asia/Calcutta",
            "workday_start_local": row[4] or "09:00",
            "workday_end_local": row[5] or "17:00",
            "focus_xp_multiplier": float(row[6] or 1.5),
        }
    finally:
        conn.close()


def get_work_items():
    conn = get_connection()
    try:
        cur = conn.cursor()
        result = task_repository.list_tasks(
            cur,
            DEFAULT_USER_ID,
            {"page": 1, "page_size": 100},
            _today_from_db(cur),
        )
        return [_dashboard_task(item) for item in result["items"]]
    finally:
        conn.close()


def get_daily_work_items(work_date):
    conn = get_connection()
    try:
        cur = conn.cursor()
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
            {"user_id": DEFAULT_USER_ID, "work_date": work_date},
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
    finally:
        conn.close()


def get_calendar_events(work_date):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                EVENT_ID,
                TITLE,
                START_AT,
                END_AT,
                DURATION_MINUTES,
                IS_MEETING,
                IS_FOCUS_BLOCK,
                ATTENDEE_COUNT,
                EXTERNAL_SOURCE
            FROM CALENDAR_EVENTS
            WHERE USER_ID = :user_id
              AND START_AT >= CAST(TO_DATE(:work_date, 'YYYY-MM-DD') AS TIMESTAMP)
              AND START_AT < CAST(TO_DATE(:work_date, 'YYYY-MM-DD') + 1 AS TIMESTAMP)
            ORDER BY START_AT
            """,
            {"user_id": DEFAULT_USER_ID, "work_date": work_date},
        )
        return [
            {
                "event_id": row[0],
                "title": row[1],
                "start_at": row[2].isoformat() if row[2] else None,
                "end_at": row[3].isoformat() if row[3] else None,
                "duration_minutes": row[4] or 0,
                "is_meeting": bool(row[5]),
                "is_focus_block": bool(row[6]),
                "attendee_count": row[7],
                "external_source": row[8],
            }
            for row in cur.fetchall()
        ]
    finally:
        conn.close()


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


def _default_user():
    return {
        "user_id": DEFAULT_USER_ID,
        "first_name": "DevQuest",
        "last_name": "User",
        "email": "",
        "timezone": "Asia/Calcutta",
        "workday_start_local": "09:00",
        "workday_end_local": "17:00",
        "focus_xp_multiplier": 1.5,
    }


def _split_display_name(value):
    parts = str(value or "DevQuest User").strip().split()
    if not parts:
        return "DevQuest", "User"
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _text(value):
    if value is None:
        return ""
    if hasattr(value, "read"):
        return value.read()
    return str(value)
