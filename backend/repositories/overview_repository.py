import json
from threading import Lock


_OVERVIEW_STORAGE_LOCK = Lock()
_OVERVIEW_STORAGE_READY = False


def ensure_overview_storage(cur):
    global _OVERVIEW_STORAGE_READY
    if _OVERVIEW_STORAGE_READY:
        return

    with _OVERVIEW_STORAGE_LOCK:
        if _OVERVIEW_STORAGE_READY:
            return

        if not sequence_exists(cur, "DAILY_OVERVIEWS_SEQ"):
            cur.execute("CREATE SEQUENCE DAILY_OVERVIEWS_SEQ START WITH 1 INCREMENT BY 1 CACHE 100 NOCYCLE")

        if not sequence_exists(cur, "WEEKLY_OVERVIEWS_SEQ"):
            cur.execute("CREATE SEQUENCE WEEKLY_OVERVIEWS_SEQ START WITH 1 INCREMENT BY 1 CACHE 100 NOCYCLE")

        if not table_exists(cur, "DAILY_OVERVIEWS"):
            cur.execute(
                """
                CREATE TABLE DAILY_OVERVIEWS (
                  DAILY_OVERVIEW_ID NUMBER(19) DEFAULT DAILY_OVERVIEWS_SEQ.NEXTVAL PRIMARY KEY,
                  USER_ID NUMBER(19) NOT NULL REFERENCES APP_USERS(USER_ID),
                  OVERVIEW_DATE DATE NOT NULL,
                  SOURCE_AI_RUN_ID NUMBER(19) REFERENCES AI_RUNS(AI_RUN_ID),
                  TASKS_COMPLETED NUMBER(8) DEFAULT 0 NOT NULL,
                  XP_EARNED NUMBER(8) DEFAULT 0 NOT NULL,
                  MEETING_MINUTES NUMBER(8) DEFAULT 0 NOT NULL,
                  FOCUS_MINUTES NUMBER(8) DEFAULT 0 NOT NULL,
                  NEW_LEARNINGS CLOB,
                  WENT_WELL CLOB,
                  WENT_WRONG CLOB,
                  SUMMARY CLOB,
                  CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
                  UPDATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
                  ROW_VERSION NUMBER DEFAULT 1 NOT NULL,
                  CONSTRAINT DAILY_OVERVIEWS_UK UNIQUE (USER_ID, OVERVIEW_DATE)
                )
                """
            )

        if not table_exists(cur, "WEEKLY_OVERVIEWS"):
            cur.execute(
                """
                CREATE TABLE WEEKLY_OVERVIEWS (
                  WEEKLY_OVERVIEW_ID NUMBER(19) DEFAULT WEEKLY_OVERVIEWS_SEQ.NEXTVAL PRIMARY KEY,
                  USER_ID NUMBER(19) NOT NULL REFERENCES APP_USERS(USER_ID),
                  WEEK_START_DATE DATE NOT NULL,
                  WEEK_END_DATE DATE NOT NULL,
                  SOURCE_AI_RUN_ID NUMBER(19) REFERENCES AI_RUNS(AI_RUN_ID),
                  TASKS_COMPLETED NUMBER(8) DEFAULT 0 NOT NULL,
                  XP_EARNED NUMBER(8) DEFAULT 0 NOT NULL,
                  MEETING_MINUTES NUMBER(8) DEFAULT 0 NOT NULL,
                  FOCUS_MINUTES NUMBER(8) DEFAULT 0 NOT NULL,
                  TOP_ACCOMPLISHMENTS CLOB,
                  NEW_LEARNINGS CLOB,
                  THEMES CLOB,
                  WENT_WELL CLOB,
                  WENT_WRONG CLOB,
                  SUMMARY CLOB,
                  CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
                  UPDATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
                  ROW_VERSION NUMBER DEFAULT 1 NOT NULL,
                  CONSTRAINT WEEKLY_OVERVIEWS_UK UNIQUE (USER_ID, WEEK_START_DATE),
                  CONSTRAINT WEEKLY_OVERVIEWS_DATE_CK CHECK (WEEK_END_DATE >= WEEK_START_DATE)
                )
                """
            )

        _OVERVIEW_STORAGE_READY = True


def fetch_daily_overview_row(cur, user_id, overview_date):
    cur.execute(
        """
        SELECT
            DAILY_OVERVIEW_ID,
            SOURCE_AI_RUN_ID,
            TASKS_COMPLETED,
            XP_EARNED,
            MEETING_MINUTES,
            FOCUS_MINUTES,
            NEW_LEARNINGS,
            WENT_WELL,
            WENT_WRONG,
            SUMMARY,
            UPDATED_AT
        FROM DAILY_OVERVIEWS
        WHERE USER_ID = :user_id
          AND OVERVIEW_DATE = TO_DATE(:overview_date, 'YYYY-MM-DD')
        """,
        {"user_id": user_id, "overview_date": overview_date},
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "daily_overview_id": row[0],
        "source_ai_run_id": row[1],
        "tasks_completed": row[2] or 0,
        "xp_earned": row[3] or 0,
        "meeting_minutes": row[4] or 0,
        "focus_minutes": row[5] or 0,
        "new_learnings": _json_list(row[6]),
        "went_well": _json_list(row[7]),
        "went_wrong": _json_list(row[8]),
        "summary": _text(row[9]),
        "updated_at": row[10].isoformat() if row[10] else None,
    }


def fetch_weekly_overview_row(cur, user_id, week_start):
    cur.execute(
        """
        SELECT
            WEEKLY_OVERVIEW_ID,
            SOURCE_AI_RUN_ID,
            WEEK_START_DATE,
            WEEK_END_DATE,
            TASKS_COMPLETED,
            XP_EARNED,
            MEETING_MINUTES,
            FOCUS_MINUTES,
            TOP_ACCOMPLISHMENTS,
            NEW_LEARNINGS,
            THEMES,
            WENT_WELL,
            WENT_WRONG,
            SUMMARY,
            UPDATED_AT
        FROM WEEKLY_OVERVIEWS
        WHERE USER_ID = :user_id
          AND WEEK_START_DATE = TO_DATE(:week_start, 'YYYY-MM-DD')
        """,
        {"user_id": user_id, "week_start": week_start},
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "weekly_overview_id": row[0],
        "source_ai_run_id": row[1],
        "week_start": row[2].isoformat()[:10] if row[2] else week_start,
        "week_end": row[3].isoformat()[:10] if row[3] else None,
        "tasks_completed": row[4] or 0,
        "xp_earned": row[5] or 0,
        "meeting_minutes": row[6] or 0,
        "focus_minutes": row[7] or 0,
        "top_accomplishments": _json_list(row[8]),
        "new_learnings": _json_list(row[9]),
        "themes": _json_list(row[10]),
        "went_well": _json_list(row[11]),
        "went_wrong": _json_list(row[12]),
        "summary": _text(row[13]),
        "updated_at": row[14].isoformat() if row[14] else None,
    }


def fetch_completed_tasks(cur, user_id, start_date, end_date):
    cur.execute(
        """
        SELECT
            TASK_ID,
            TITLE,
            DESCRIPTION,
            TASK_TYPE,
            PRIORITY,
            STATUS,
            ESTIMATED_MINUTES,
            ACTUAL_MINUTES,
            XP_VALUE,
            NOTES,
            LABELS_JSON,
            AI_CATEGORY,
            AI_INSIGHT,
            COMPLETED_AT
        FROM WORK_ITEMS
        WHERE USER_ID = :user_id
          AND STATUS = 'Done'
          AND COMPLETED_AT >= CAST(TO_DATE(:start_date, 'YYYY-MM-DD') AS TIMESTAMP)
          AND COMPLETED_AT < CAST(TO_DATE(:end_date, 'YYYY-MM-DD') + 1 AS TIMESTAMP)
        ORDER BY COMPLETED_AT
        """,
        {"user_id": user_id, "start_date": start_date, "end_date": end_date},
    )
    return [_task_row(row) for row in cur.fetchall()]


def fetch_worked_tasks(cur, user_id, start_date, end_date):
    cur.execute(
        """
        SELECT
            w.TASK_ID,
            w.TITLE,
            w.DESCRIPTION,
            w.TASK_TYPE,
            w.PRIORITY,
            w.STATUS,
            w.ESTIMATED_MINUTES,
            NVL(d.ACTUAL_MINUTES, w.ACTUAL_MINUTES) AS ACTUAL_MINUTES,
            w.XP_VALUE,
            NVL(d.NOTES, w.NOTES) AS NOTES,
            w.LABELS_JSON,
            w.AI_CATEGORY,
            w.AI_INSIGHT,
            w.COMPLETED_AT,
            TO_CHAR(d.WORK_DATE, 'YYYY-MM-DD') AS WORK_DATE,
            d.PLANNED_MINUTES
        FROM WORK_ITEM_WORK_DATES d
        JOIN WORK_ITEMS w
          ON w.TASK_ID = d.TASK_ID
         AND w.USER_ID = d.USER_ID
        WHERE d.USER_ID = :user_id
          AND d.WORK_DATE BETWEEN TO_DATE(:start_date, 'YYYY-MM-DD')
                              AND TO_DATE(:end_date, 'YYYY-MM-DD')
        ORDER BY d.WORK_DATE, NVL(w.AI_PRIORITY_SCORE, 0) DESC, w.TITLE
        """,
        {"user_id": user_id, "start_date": start_date, "end_date": end_date},
    )
    return [_task_row(row, work_date=row[14], planned_minutes=row[15]) for row in cur.fetchall()]


def fetch_calendar_events(cur, user_id, start_date, end_date):
    if not table_exists(cur, "CALENDAR_EVENTS"):
        return []
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
          AND START_AT >= CAST(TO_DATE(:start_date, 'YYYY-MM-DD') AS TIMESTAMP)
          AND START_AT < CAST(TO_DATE(:end_date, 'YYYY-MM-DD') + 1 AS TIMESTAMP)
        ORDER BY START_AT
        """,
        {"user_id": user_id, "start_date": start_date, "end_date": end_date},
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


def fetch_focus_sessions(cur, user_id, start_date, end_date):
    if not table_exists(cur, "FOCUS_SESSIONS"):
        return []
    cur.execute(
        """
        SELECT
            f.FOCUS_SESSION_ID,
            f.TASK_ID,
            w.TITLE,
            f.SESSION_DATE,
            f.STARTED_AT,
            f.ENDED_AT,
            f.PLANNED_MINUTES,
            f.ACTUAL_MINUTES,
            f.STATUS,
            f.XP_AWARDED,
            f.NOTES
        FROM FOCUS_SESSIONS f
        LEFT JOIN WORK_ITEMS w
          ON w.TASK_ID = f.TASK_ID
         AND w.USER_ID = f.USER_ID
        WHERE f.USER_ID = :user_id
          AND f.SESSION_DATE BETWEEN TO_DATE(:start_date, 'YYYY-MM-DD')
                                 AND TO_DATE(:end_date, 'YYYY-MM-DD')
        ORDER BY f.STARTED_AT
        """,
        {"user_id": user_id, "start_date": start_date, "end_date": end_date},
    )
    return [
        {
            "focus_session_id": row[0],
            "task_id": row[1],
            "task_title": row[2] or "Focus session",
            "session_date": row[3].isoformat()[:10] if row[3] else None,
            "started_at": row[4].isoformat() if row[4] else None,
            "ended_at": row[5].isoformat() if row[5] else None,
            "planned_minutes": row[6] or 0,
            "actual_minutes": row[7] or 0,
            "status": row[8],
            "xp_awarded": row[9] or 0,
            "notes": row[10] or "",
        }
        for row in cur.fetchall()
    ]


def fetch_daily_overviews(cur, user_id, start_date, end_date):
    if not table_exists(cur, "DAILY_OVERVIEWS"):
        return []
    cur.execute(
        """
        SELECT
            TO_CHAR(OVERVIEW_DATE, 'YYYY-MM-DD'),
            TASKS_COMPLETED,
            XP_EARNED,
            MEETING_MINUTES,
            FOCUS_MINUTES,
            NEW_LEARNINGS,
            WENT_WELL,
            WENT_WRONG,
            SUMMARY,
            UPDATED_AT
        FROM DAILY_OVERVIEWS
        WHERE USER_ID = :user_id
          AND OVERVIEW_DATE BETWEEN TO_DATE(:start_date, 'YYYY-MM-DD')
                                AND TO_DATE(:end_date, 'YYYY-MM-DD')
        ORDER BY OVERVIEW_DATE
        """,
        {"user_id": user_id, "start_date": start_date, "end_date": end_date},
    )
    return [
        {
            "date": row[0],
            "tasks_completed": row[1] or 0,
            "xp_earned": row[2] or 0,
            "meeting_minutes": row[3] or 0,
            "focus_minutes": row[4] or 0,
            "new_learnings": _json_list(row[5]),
            "went_well": _json_list(row[6]),
            "went_wrong": _json_list(row[7]),
            "summary": _text(row[8]),
            "updated_at": row[9].isoformat() if row[9] else None,
        }
        for row in cur.fetchall()
    ]


def fetch_daily_overviews_for_week(cur, user_id, week_start, week_end):
    return fetch_daily_overviews(cur, user_id, week_start, week_end)


def insert_ai_run(cur, user_id, run_type, model_id, request_payload):
    if not table_exists(cur, "AI_RUNS"):
        return None
    ai_run_id = cur.var(int)
    cur.execute(
        """
        INSERT INTO AI_RUNS (
            AI_RUN_ID,
            USER_ID,
            RUN_TYPE,
            STATUS,
            PROVIDER,
            MODEL_ID,
            REQUEST_JSON,
            STARTED_AT,
            CREATED_AT
        )
        VALUES (
            AI_RUNS_SEQ.NEXTVAL,
            :user_id,
            :run_type,
            'RUNNING',
            'OCI',
            :model_id,
            :request_json,
            SYSTIMESTAMP,
            SYSTIMESTAMP
        )
        RETURNING AI_RUN_ID INTO :ai_run_id
        """,
        {
            "user_id": user_id,
            "run_type": run_type,
            "model_id": model_id,
            "request_json": json.dumps(request_payload, separators=(",", ":"), default=str),
            "ai_run_id": ai_run_id,
        },
    )
    value = ai_run_id.getvalue()
    return value[0] if isinstance(value, list) else value


def update_ai_run(cur, ai_run_id, status, response_payload=None, error_code=None, error_message=None):
    if not ai_run_id or not table_exists(cur, "AI_RUNS"):
        return
    cur.execute(
        """
        UPDATE AI_RUNS
        SET STATUS = :status,
            RESPONSE_JSON = :response_json,
            ERROR_CODE = :error_code,
            ERROR_MESSAGE = :error_message,
            COMPLETED_AT = SYSTIMESTAMP
        WHERE AI_RUN_ID = :ai_run_id
        """,
        {
            "ai_run_id": ai_run_id,
            "status": status,
            "response_json": json.dumps(response_payload, separators=(",", ":"), default=str) if response_payload is not None else None,
            "error_code": error_code,
            "error_message": error_message,
        },
    )


def upsert_daily_overview(cur, user_id, overview_date, ai_run_id, overview):
    cur.execute(
        """
        MERGE INTO DAILY_OVERVIEWS target
        USING (
            SELECT :user_id USER_ID, TO_DATE(:overview_date, 'YYYY-MM-DD') OVERVIEW_DATE
            FROM DUAL
        ) source
        ON (target.USER_ID = source.USER_ID AND target.OVERVIEW_DATE = source.OVERVIEW_DATE)
        WHEN MATCHED THEN UPDATE SET
            SOURCE_AI_RUN_ID = :ai_run_id,
            TASKS_COMPLETED = :tasks_completed,
            XP_EARNED = :xp_earned,
            MEETING_MINUTES = :meeting_minutes,
            FOCUS_MINUTES = :focus_minutes,
            NEW_LEARNINGS = :new_learnings,
            WENT_WELL = :went_well,
            WENT_WRONG = :went_wrong,
            SUMMARY = :summary,
            UPDATED_AT = SYSTIMESTAMP,
            ROW_VERSION = ROW_VERSION + 1
        WHEN NOT MATCHED THEN INSERT (
            DAILY_OVERVIEW_ID,
            USER_ID,
            OVERVIEW_DATE,
            SOURCE_AI_RUN_ID,
            TASKS_COMPLETED,
            XP_EARNED,
            MEETING_MINUTES,
            FOCUS_MINUTES,
            NEW_LEARNINGS,
            WENT_WELL,
            WENT_WRONG,
            SUMMARY,
            CREATED_AT,
            UPDATED_AT,
            ROW_VERSION
        )
        VALUES (
            DAILY_OVERVIEWS_SEQ.NEXTVAL,
            :user_id,
            TO_DATE(:overview_date, 'YYYY-MM-DD'),
            :ai_run_id,
            :tasks_completed,
            :xp_earned,
            :meeting_minutes,
            :focus_minutes,
            :new_learnings,
            :went_well,
            :went_wrong,
            :summary,
            SYSTIMESTAMP,
            SYSTIMESTAMP,
            1
        )
        """,
        _overview_binds(user_id, overview_date, ai_run_id, overview),
    )


def upsert_weekly_overview(cur, user_id, week_start, week_end, ai_run_id, overview):
    binds = _overview_binds(user_id, week_start, ai_run_id, overview)
    binds["week_end"] = week_end
    binds["top_accomplishments"] = _json(overview.get("top_accomplishments", []))
    binds["themes"] = _json(overview.get("themes", []))
    binds["went_well"] = _json(overview.get("went_well", []))
    binds["went_wrong"] = _json(overview.get("went_wrong", []))
    cur.execute(
        """
        MERGE INTO WEEKLY_OVERVIEWS target
        USING (
            SELECT :user_id USER_ID, TO_DATE(:overview_date, 'YYYY-MM-DD') WEEK_START_DATE
            FROM DUAL
        ) source
        ON (target.USER_ID = source.USER_ID AND target.WEEK_START_DATE = source.WEEK_START_DATE)
        WHEN MATCHED THEN UPDATE SET
            WEEK_END_DATE = TO_DATE(:week_end, 'YYYY-MM-DD'),
            SOURCE_AI_RUN_ID = :ai_run_id,
            TASKS_COMPLETED = :tasks_completed,
            XP_EARNED = :xp_earned,
            MEETING_MINUTES = :meeting_minutes,
            FOCUS_MINUTES = :focus_minutes,
            TOP_ACCOMPLISHMENTS = :top_accomplishments,
            NEW_LEARNINGS = :new_learnings,
            THEMES = :themes,
            WENT_WELL = :went_well,
            WENT_WRONG = :went_wrong,
            SUMMARY = :summary,
            UPDATED_AT = SYSTIMESTAMP,
            ROW_VERSION = ROW_VERSION + 1
        WHEN NOT MATCHED THEN INSERT (
            WEEKLY_OVERVIEW_ID,
            USER_ID,
            WEEK_START_DATE,
            WEEK_END_DATE,
            SOURCE_AI_RUN_ID,
            TASKS_COMPLETED,
            XP_EARNED,
            MEETING_MINUTES,
            FOCUS_MINUTES,
            TOP_ACCOMPLISHMENTS,
            NEW_LEARNINGS,
            THEMES,
            WENT_WELL,
            WENT_WRONG,
            SUMMARY,
            CREATED_AT,
            UPDATED_AT,
            ROW_VERSION
        )
        VALUES (
            WEEKLY_OVERVIEWS_SEQ.NEXTVAL,
            :user_id,
            TO_DATE(:overview_date, 'YYYY-MM-DD'),
            TO_DATE(:week_end, 'YYYY-MM-DD'),
            :ai_run_id,
            :tasks_completed,
            :xp_earned,
            :meeting_minutes,
            :focus_minutes,
            :top_accomplishments,
            :new_learnings,
            :themes,
            :went_well,
            :went_wrong,
            :summary,
            SYSTIMESTAMP,
            SYSTIMESTAMP,
            1
        )
        """,
        binds,
    )


def _task_row(row, work_date=None, planned_minutes=None):
    return {
        "task_id": row[0],
        "title": row[1],
        "description": _text(row[2]),
        "task_type": row[3],
        "priority": row[4],
        "status": row[5],
        "estimated_minutes": row[6] or 0,
        "actual_minutes": row[7] or 0,
        "xp_value": row[8] or 0,
        "notes": _text(row[9]),
        "labels": _json_list(row[10]),
        "ai_category": row[11],
        "ai_insight": _text(row[12]),
        "completed_at": row[13].isoformat() if row[13] else None,
        "work_date": work_date,
        "planned_minutes": planned_minutes,
    }


def _json(value):
    return json.dumps(value or [], separators=(",", ":"))


def _json_list(value):
    value = _text(value)
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else [str(parsed)]
    except (TypeError, ValueError):
        return [item.strip() for item in str(value).splitlines() if item.strip()]


def _text(value):
    if value is None:
        return ""
    if hasattr(value, "read"):
        return value.read()
    return str(value)


def table_exists(cur, table_name):
    cur.execute(
        "SELECT COUNT(*) FROM USER_TABLES WHERE TABLE_NAME = :table_name",
        {"table_name": table_name.upper()},
    )
    return cur.fetchone()[0] > 0


def sequence_exists(cur, sequence_name):
    cur.execute(
        "SELECT COUNT(*) FROM USER_SEQUENCES WHERE SEQUENCE_NAME = :sequence_name",
        {"sequence_name": sequence_name.upper()},
    )
    return cur.fetchone()[0] > 0


def _overview_binds(user_id, overview_date, ai_run_id, overview):
    return {
        "user_id": user_id,
        "overview_date": overview_date,
        "ai_run_id": ai_run_id,
        "tasks_completed": overview.get("tasks_completed", 0),
        "xp_earned": overview.get("xp_earned", 0),
        "meeting_minutes": overview.get("meeting_minutes", 0),
        "focus_minutes": overview.get("focus_minutes", 0),
        "new_learnings": _json(overview.get("new_learnings", [])),
        "went_well": _json(overview.get("went_well", [])),
        "went_wrong": _json(overview.get("went_wrong", [])),
        "summary": overview.get("summary") or "",
    }
