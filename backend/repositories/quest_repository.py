from repositories import task_repository


def latest_quest_plan(cur, user_id, quest_date):
    cur.execute(
        """
        SELECT
            QUEST_PLAN_ID,
            SOURCE_AI_RUN_ID,
            CAPACITY_MINUTES,
            MEETING_MINUTES,
            FOCUS_MINUTES,
            SUMMARY,
            CREATED_AT,
            UPDATED_AT
        FROM QUEST_PLANS
        WHERE USER_ID = :user_id
          AND QUEST_DATE = TO_DATE(:quest_date, 'YYYY-MM-DD')
        ORDER BY UPDATED_AT DESC, CREATED_AT DESC, QUEST_PLAN_ID DESC
        FETCH FIRST 1 ROW ONLY
        """,
        {"user_id": user_id, "quest_date": quest_date},
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "quest_plan_id": row[0],
        "user_id": user_id,
        "quest_date": quest_date,
        "source_ai_run_id": row[1],
        "capacity": {
            "available_focus_minutes": row[2] or 0,
            "meeting_minutes": row[3] or 0,
            "focus_minutes": row[4] or 0,
        },
        "summary": _text(row[5]),
        "created_at": row[6].isoformat() if row[6] else None,
        "updated_at": row[7].isoformat() if row[7] else None,
    }


def fetch_quest_items(cur, user_id, quest_plan_id, work_date):
    cur.execute(
        f"""
        SELECT
            qi.RANK_ORDER,
            qi.REASON,
            TO_CHAR(qi.SUGGESTED_START_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            TO_CHAR(qi.SUGGESTED_END_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            qi.XP_VALUE,
            {task_repository.TASK_SELECT.strip()[6:]}
        JOIN QUEST_ITEMS qi
          ON qi.USER_ID = w.USER_ID
         AND qi.TASK_ID = w.TASK_ID
        WHERE qi.USER_ID = :user_id
          AND qi.QUEST_PLAN_ID = :quest_plan_id
        ORDER BY qi.RANK_ORDER, qi.QUEST_ITEM_ID
        """,
        {"user_id": user_id, "quest_plan_id": quest_plan_id, "work_date": work_date},
    )
    output = []
    for row in cur.fetchall():
        quest = {
            "rank_order": row[0],
            "reason": _text(row[1]),
            "suggested_start_at": row[2],
            "suggested_end_at": row[3],
            "xp_value": row[4] or 0,
        }
        task = task_repository._task_row(row[5:])
        output.append((task, quest))
    return output


def upsert_quest_plan(cur, user_id, quest_date, ai_run_id, ai, capacity):
    existing = latest_quest_plan(cur, user_id, quest_date)
    if existing:
        cur.execute(
            """
            UPDATE QUEST_PLANS
            SET SOURCE_AI_RUN_ID = :ai_run_id,
                CAPACITY_MINUTES = :capacity_minutes,
                MEETING_MINUTES = :meeting_minutes,
                FOCUS_MINUTES = :focus_minutes,
                SUMMARY = :summary,
                UPDATED_AT = SYSTIMESTAMP
            WHERE USER_ID = :user_id
              AND QUEST_PLAN_ID = :quest_plan_id
            """,
            {
                "user_id": user_id,
                "quest_plan_id": existing["quest_plan_id"],
                "ai_run_id": ai_run_id,
                "capacity_minutes": capacity.get("available_focus_minutes", 0),
                "meeting_minutes": capacity.get("meeting_minutes", 0),
                "focus_minutes": capacity.get("focus_block_minutes", 0),
                "summary": ai.get("summary") or "",
            },
        )
        return existing["quest_plan_id"]

    quest_plan_id = cur.var(int)
    cur.execute(
        """
        INSERT INTO QUEST_PLANS (
            QUEST_PLAN_ID,
            USER_ID,
            QUEST_DATE,
            SOURCE_AI_RUN_ID,
            CAPACITY_MINUTES,
            MEETING_MINUTES,
            FOCUS_MINUTES,
            SUMMARY,
            CREATED_AT,
            UPDATED_AT
        )
        VALUES (
            QUEST_PLANS_SEQ.NEXTVAL,
            :user_id,
            TO_DATE(:quest_date, 'YYYY-MM-DD'),
            :ai_run_id,
            :capacity_minutes,
            :meeting_minutes,
            :focus_minutes,
            :summary,
            SYSTIMESTAMP,
            SYSTIMESTAMP
        )
        RETURNING QUEST_PLAN_ID INTO :quest_plan_id
        """,
        {
            "user_id": user_id,
            "quest_date": quest_date,
            "ai_run_id": ai_run_id,
            "capacity_minutes": capacity.get("available_focus_minutes", 0),
            "meeting_minutes": capacity.get("meeting_minutes", 0),
            "focus_minutes": capacity.get("focus_block_minutes", 0),
            "summary": ai.get("summary") or "",
            "quest_plan_id": quest_plan_id,
        },
    )
    return _returned_id(quest_plan_id)


def replace_quest_items(cur, user_id, quest_plan_id, quests):
    cur.execute(
        "DELETE FROM QUEST_ITEMS WHERE USER_ID = :user_id AND QUEST_PLAN_ID = :quest_plan_id",
        {"user_id": user_id, "quest_plan_id": quest_plan_id},
    )
    for quest in quests:
        cur.execute(
            """
            INSERT INTO QUEST_ITEMS (
                QUEST_ITEM_ID,
                USER_ID,
                QUEST_PLAN_ID,
                TASK_ID,
                RANK_ORDER,
                REASON,
                SUGGESTED_START_AT,
                SUGGESTED_END_AT,
                XP_VALUE,
                CREATED_AT
            )
            VALUES (
                QUEST_ITEMS_SEQ.NEXTVAL,
                :user_id,
                :quest_plan_id,
                :task_id,
                :rank_order,
                :reason,
                TO_TIMESTAMP_TZ(:suggested_start_at, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
                TO_TIMESTAMP_TZ(:suggested_end_at, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
                :xp_value,
                SYSTIMESTAMP
            )
            """,
            {
                "user_id": user_id,
                "quest_plan_id": quest_plan_id,
                "task_id": quest.get("task_id"),
                "rank_order": quest.get("rank_order"),
                "reason": quest.get("reason") or "",
                "suggested_start_at": quest.get("suggested_start_at"),
                "suggested_end_at": quest.get("suggested_end_at"),
                "xp_value": quest.get("xp_value"),
            },
        )


def mark_quest_tasks_working(cur, user_id, quest_date, quests):
    for quest in quests:
        task_id = quest.get("task_id")
        task_repository.insert_work_date(cur, user_id, task_id, quest_date, quest.get("xp_value"))
        cur.execute(
            """
            UPDATE WORK_ITEMS
            SET STATUS = CASE WHEN STATUS NOT IN ('Done', 'Blocked') THEN 'In Progress' ELSE STATUS END,
                UPDATED_AT = SYSTIMESTAMP,
                ROW_VERSION = ROW_VERSION + 1
            WHERE USER_ID = :user_id
              AND TASK_ID = :task_id
            """,
            {"user_id": user_id, "task_id": task_id},
        )


def _returned_id(var):
    value = var.getvalue()
    return value[0] if isinstance(value, list) else value


def _text(value):
    if value is None:
        return ""
    if hasattr(value, "read"):
        return value.read()
    return str(value)
