from __future__ import annotations


def list_focus_sessions(cur, user_id, date_from=None, date_to=None):
    where = ["fs.USER_ID = :user_id"]
    binds = {"user_id": user_id}

    if date_from:
        where.append("fs.SESSION_DATE >= TO_DATE(:date_from, 'YYYY-MM-DD')")
        binds["date_from"] = date_from
    if date_to:
        where.append("fs.SESSION_DATE <= TO_DATE(:date_to, 'YYYY-MM-DD')")
        binds["date_to"] = date_to

    cur.execute(
        f"""
        SELECT
            fs.FOCUS_SESSION_ID,
            fs.CLIENT_FOCUS_SESSION_ID,
            fs.USER_ID,
            fs.TASK_ID,
            w.TITLE,
            fs.QUEST_ITEM_ID,
            TO_CHAR(fs.SESSION_DATE, 'YYYY-MM-DD'),
            TO_CHAR(fs.STARTED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            TO_CHAR(fs.ENDED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            fs.DURATION_SECONDS,
            fs.DURATION_MINUTES,
            fs.OUTCOME_TYPE,
            fs.OUTCOME_NOTE,
            fs.STATUS,
            fs.XP_MULTIPLIER,
            fs.XP_AWARDED,
            TO_CHAR(fs.CREATED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            TO_CHAR(fs.UPDATED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            fs.ROW_VERSION,
            qi.CLIENT_QUEST_ITEM_ID
        FROM FOCUS_SESSIONS fs
        LEFT JOIN WORK_ITEMS w
          ON TO_CHAR(w.TASK_ID) = fs.TASK_ID
         AND w.USER_ID = fs.USER_ID
        LEFT JOIN QUEST_ITEMS qi
          ON qi.QUEST_ITEM_ID = fs.QUEST_ITEM_ID
        WHERE {' AND '.join(where)}
        ORDER BY fs.STARTED_AT DESC, fs.FOCUS_SESSION_ID DESC
        """,
        binds,
    )
    return [_row_to_session(row) for row in cur.fetchall()]


def resolve_quest_item_id(cur, user_id, client_quest_item_id):
    if not client_quest_item_id:
        return None
    cur.execute(
        """
        SELECT qi.QUEST_ITEM_ID
        FROM QUEST_ITEMS qi
        JOIN QUEST_PLANS qp
          ON qp.QUEST_PLAN_ID = qi.QUEST_PLAN_ID
        WHERE qp.USER_ID = :user_id
          AND qi.CLIENT_QUEST_ITEM_ID = :client_quest_item_id
        FETCH FIRST 1 ROWS ONLY
        """,
        {"user_id": user_id, "client_quest_item_id": client_quest_item_id},
    )
    row = cur.fetchone()
    return int(row[0]) if row else None


def fetch_task_reward_context(cur, user_id, task_id):
    if not task_id:
        return {"xp_value": 0, "estimated_minutes": 60, "title": ""}
    cur.execute(
        """
        SELECT NVL(XP_VALUE, 0), NVL(ESTIMATED_MINUTES, 60), TITLE
        FROM WORK_ITEMS
        WHERE USER_ID = :user_id
          AND TO_CHAR(TASK_ID) = :task_id
        FETCH FIRST 1 ROWS ONLY
        """,
        {"user_id": user_id, "task_id": str(task_id)},
    )
    row = cur.fetchone()
    if not row:
        return {"xp_value": 0, "estimated_minutes": 60, "title": ""}
    return {
        "xp_value": int(row[0] or 0),
        "estimated_minutes": int(row[1] or 60),
        "title": row[2] or "",
    }


def fetch_focus_multiplier(cur, user_id):
    cur.execute(
        """
        SELECT NVL(FOCUS_XP_MULTIPLIER, 1)
        FROM APP_USERS
        WHERE USER_ID = :user_id
        """,
        {"user_id": user_id},
    )
    row = cur.fetchone()
    return float(row[0]) if row else 1.0


def insert_focus_session(cur, user_id, payload, quest_item_id, xp_multiplier, xp_awarded):
    out_var = cur.var(int)
    cur.execute(
        """
        INSERT INTO FOCUS_SESSIONS (
            FOCUS_SESSION_ID,
            CLIENT_FOCUS_SESSION_ID,
            USER_ID,
            TASK_ID,
            QUEST_ITEM_ID,
            SESSION_DATE,
            STARTED_AT,
            ENDED_AT,
            DURATION_SECONDS,
            DURATION_MINUTES,
            OUTCOME_TYPE,
            OUTCOME_NOTE,
            STATUS,
            XP_MULTIPLIER,
            XP_AWARDED,
            CREATED_AT,
            UPDATED_AT,
            ROW_VERSION
        )
        VALUES (
            FOCUS_SESSIONS_SEQ.NEXTVAL,
            :client_focus_session_id,
            :user_id,
            :task_id,
            :quest_item_id,
            TO_DATE(:session_date, 'YYYY-MM-DD'),
            :started_at,
            :ended_at,
            :duration_seconds,
            :duration_minutes,
            :outcome_type,
            :outcome_note,
            :status,
            :xp_multiplier,
            :xp_awarded,
            SYSTIMESTAMP,
            SYSTIMESTAMP,
            1
        )
        RETURNING FOCUS_SESSION_ID INTO :focus_session_id
        """,
        {
            "client_focus_session_id": payload.get("client_focus_session_id"),
            "user_id": user_id,
            "task_id": payload.get("task_id"),
            "quest_item_id": quest_item_id,
            "session_date": payload["session_date"],
            "started_at": payload["started_at"],
            "ended_at": payload.get("ended_at"),
            "duration_seconds": payload["duration_seconds"],
            "duration_minutes": payload["duration_minutes"],
            "outcome_type": payload.get("outcome_type"),
            "outcome_note": payload.get("outcome_note"),
            "status": payload["status"],
            "xp_multiplier": xp_multiplier,
            "xp_awarded": xp_awarded,
            "focus_session_id": out_var,
        },
    )
    return _returned_id(out_var)


def fetch_focus_session(cur, user_id, focus_session_id):
    cur.execute(
        """
        SELECT
            fs.FOCUS_SESSION_ID,
            fs.CLIENT_FOCUS_SESSION_ID,
            fs.USER_ID,
            fs.TASK_ID,
            w.TITLE,
            fs.QUEST_ITEM_ID,
            TO_CHAR(fs.SESSION_DATE, 'YYYY-MM-DD'),
            TO_CHAR(fs.STARTED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            TO_CHAR(fs.ENDED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            fs.DURATION_SECONDS,
            fs.DURATION_MINUTES,
            fs.OUTCOME_TYPE,
            fs.OUTCOME_NOTE,
            fs.STATUS,
            fs.XP_MULTIPLIER,
            fs.XP_AWARDED,
            TO_CHAR(fs.CREATED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            TO_CHAR(fs.UPDATED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            fs.ROW_VERSION,
            qi.CLIENT_QUEST_ITEM_ID
        FROM FOCUS_SESSIONS fs
        LEFT JOIN WORK_ITEMS w
          ON TO_CHAR(w.TASK_ID) = fs.TASK_ID
         AND w.USER_ID = fs.USER_ID
        LEFT JOIN QUEST_ITEMS qi
          ON qi.QUEST_ITEM_ID = fs.QUEST_ITEM_ID
        WHERE fs.USER_ID = :user_id
          AND fs.FOCUS_SESSION_ID = :focus_session_id
        """,
        {"user_id": user_id, "focus_session_id": focus_session_id},
    )
    row = cur.fetchone()
    return _row_to_session(row) if row else None


def sync_quest_focus(cur, quest_item_id, duration_minutes, xp_multiplier, xp_awarded):
    if not quest_item_id:
        return
    cur.execute(
        """
        UPDATE QUEST_ITEMS
        SET FOCUS_MINUTES = NVL(FOCUS_MINUTES, 0) + :duration_minutes,
            HAS_FOCUS_REWARD = CASE WHEN :xp_multiplier > 1 THEN 1 ELSE HAS_FOCUS_REWARD END,
            REWARD_MULTIPLIER = CASE WHEN :xp_multiplier > 1 THEN :xp_multiplier ELSE REWARD_MULTIPLIER END,
            FOCUS_BONUS_XP = GREATEST(0, :xp_awarded - NVL(BASE_XP, 0)),
            REWARD_XP = CASE WHEN :xp_awarded > NVL(REWARD_XP, 0) THEN :xp_awarded ELSE REWARD_XP END,
            UPDATED_AT = SYSTIMESTAMP,
            ROW_VERSION = ROW_VERSION + 1
        WHERE QUEST_ITEM_ID = :quest_item_id
        """,
        {
            "quest_item_id": quest_item_id,
            "duration_minutes": duration_minutes,
            "xp_multiplier": xp_multiplier,
            "xp_awarded": xp_awarded,
        },
    )


def _row_to_session(row):
    return {
        "focus_session_id": row[0],
        "client_focus_session_id": row[1],
        "user_id": row[2],
        "task_id": row[3],
        "task_title": row[4] or "",
        "quest_item_id": row[5],
        "quest_id": row[19],
        "work_date": row[6],
        "session_date": row[6],
        "started_at": row[7],
        "ended_at": row[8],
        "duration_seconds": int(row[9] or 0),
        "duration_minutes": int(row[10] or 0),
        "outcome_type": row[11] or "",
        "outcome_note": _text(row[12]),
        "status": row[13],
        "xp_multiplier": float(row[14] or 1),
        "xp_awarded": int(row[15] or 0),
        "created_at": row[16],
        "updated_at": row[17],
        "row_version": int(row[18] or 1),
    }


def _text(value):
    if value is None:
        return ""
    if hasattr(value, "read"):
        return value.read()
    return str(value)


def _returned_id(var):
    value = var.getvalue()
    return value[0] if isinstance(value, list) else value
