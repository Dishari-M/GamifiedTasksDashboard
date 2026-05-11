from __future__ import annotations

import json

from repositories import task_repository


OPEN_STATES = {"ACTIVE", "QUEUED"}


def _focus_seconds(value_seconds, value_minutes):
    if value_seconds is not None:
        return int(value_seconds or 0)
    return int(value_minutes or 0) * 60


def latest_quest_plan(cur, user_id, quest_date):
    plan = fetch_today_plan(cur, user_id, quest_date)
    if not plan:
        return None
    return {
        "quest_plan_id": plan["quest_plan_id"],
        "user_id": user_id,
        "quest_date": quest_date,
        "source_ai_run_id": plan.get("source_ai_run_id"),
        "capacity": {
            "available_focus_minutes": plan.get("capacity_minutes", 0),
            "meeting_minutes": plan.get("meeting_minutes", 0),
            "focus_seconds": plan.get("focus_seconds", plan.get("focus_minutes", 0) * 60),
            "focus_minutes": plan.get("focus_minutes", 0),
        },
        "summary": plan.get("summary") or "",
        "created_at": plan.get("created_at"),
        "updated_at": plan.get("updated_at"),
    }


def fetch_quest_items(cur, user_id, quest_plan_id, work_date):
    cur.execute(
        f"""
        SELECT
            qi.RANK_ORDER,
            qi.REASON,
            TO_CHAR(qi.SUGGESTED_START_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            TO_CHAR(qi.SUGGESTED_END_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            qi.REWARD_XP,
            {task_repository.TASK_SELECT.strip()[6:]}
        JOIN QUEST_ITEMS qi
          ON qi.TASK_ID = TO_CHAR(w.TASK_ID)
        JOIN QUEST_PLANS qp
          ON qp.QUEST_PLAN_ID = qi.QUEST_PLAN_ID
         AND qp.USER_ID = w.USER_ID
        WHERE qp.USER_ID = :user_id
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
    _ensure_focus_seconds_columns(cur)
    focus_seconds = _focus_seconds(capacity.get("focus_block_seconds"), capacity.get("focus_block_minutes"))
    existing = fetch_today_plan(cur, user_id, quest_date)
    if existing:
        cur.execute(
            """
            UPDATE QUEST_PLANS
            SET SOURCE_AI_RUN_ID = :ai_run_id,
                CAPACITY_MINUTES = :capacity_minutes,
                MEETING_MINUTES = :meeting_minutes,
                FOCUS_SECONDS = :focus_seconds,
                FOCUS_MINUTES = :focus_minutes,
                SUMMARY = :summary,
                UPDATED_AT = SYSTIMESTAMP,
                ROW_VERSION = ROW_VERSION + 1
            WHERE USER_ID = :user_id
              AND QUEST_PLAN_ID = :quest_plan_id
            """,
            {
                "user_id": user_id,
                "quest_plan_id": existing["quest_plan_id"],
                "ai_run_id": ai_run_id,
                "capacity_minutes": capacity.get("available_focus_minutes", 0),
                "meeting_minutes": capacity.get("meeting_minutes", 0),
                "focus_seconds": focus_seconds,
                "focus_minutes": focus_seconds // 60,
                "summary": ai.get("summary") or "",
            },
        )
        return existing["quest_plan_id"]

    quest_plan_id = cur.var(int)
    cur.execute(
        """
        INSERT INTO QUEST_PLANS (
            QUEST_PLAN_ID,
            CLIENT_QUEST_RUN_ID,
            USER_ID,
            QUEST_DATE,
            GENERATED_AT,
            SOURCE_TASK_IDS_JSON,
            ACTIVE_QUEST_ITEM_ID,
            STATUS,
            CAPACITY_MINUTES,
            MEETING_MINUTES,
            FOCUS_SECONDS,
            FOCUS_MINUTES,
            SUMMARY,
            SOURCE_AI_RUN_ID,
            CREATED_AT,
            UPDATED_AT,
            ROW_VERSION
        )
        VALUES (
            QUEST_PLANS_SEQ.NEXTVAL,
            :client_quest_run_id,
            :user_id,
            TO_DATE(:quest_date, 'YYYY-MM-DD'),
            SYSTIMESTAMP,
            '[]',
            NULL,
            'ACTIVE',
            :capacity_minutes,
            :meeting_minutes,
            :focus_seconds,
            :focus_minutes,
            :summary,
            :ai_run_id,
            SYSTIMESTAMP,
            SYSTIMESTAMP,
            1
        )
        RETURNING QUEST_PLAN_ID INTO :quest_plan_id
        """,
        {
            "client_quest_run_id": f"legacy-quest-run-{quest_date}",
            "user_id": user_id,
            "quest_date": quest_date,
            "ai_run_id": ai_run_id,
            "capacity_minutes": capacity.get("available_focus_minutes", 0),
            "meeting_minutes": capacity.get("meeting_minutes", 0),
            "focus_seconds": focus_seconds,
            "focus_minutes": focus_seconds // 60,
            "summary": ai.get("summary") or "",
            "quest_plan_id": quest_plan_id,
        },
    )
    return _returned_id(quest_plan_id)


def replace_quest_items(cur, user_id, quest_plan_id, quests):
    _ensure_focus_seconds_columns(cur)
    cur.execute(
        """
        UPDATE QUEST_PLANS
        SET ACTIVE_QUEST_ITEM_ID = NULL,
            UPDATED_AT = SYSTIMESTAMP,
            ROW_VERSION = ROW_VERSION + 1
        WHERE USER_ID = :user_id
          AND QUEST_PLAN_ID = :quest_plan_id
        """,
        {"user_id": user_id, "quest_plan_id": quest_plan_id},
    )
    cur.execute("DELETE FROM QUEST_ITEMS WHERE QUEST_PLAN_ID = :quest_plan_id", {"quest_plan_id": quest_plan_id})
    for quest in quests:
        cur.execute(
            """
            INSERT INTO QUEST_ITEMS (
                QUEST_ITEM_ID,
                QUEST_PLAN_ID,
                CLIENT_QUEST_ITEM_ID,
                TASK_ID,
                RANK_ORDER,
                STATE,
                REASON_LABEL,
                REASON,
                ACTION_LABEL,
                BASE_XP,
                REWARD_XP,
                FOCUS_BONUS_XP,
                REWARD_MULTIPLIER,
                HAS_FOCUS_REWARD,
                FOCUS_TARGET_MINUTES,
                FOCUS_SECONDS,
                FOCUS_MINUTES,
                SUGGESTED_START_AT,
                SUGGESTED_END_AT,
                STARTED_AT,
                COMPLETED_AT,
                SKIPPED_AT,
                SKIP_REASON,
                CREATED_AT,
                UPDATED_AT,
                ROW_VERSION
            )
            VALUES (
                QUEST_ITEMS_SEQ.NEXTVAL,
                :quest_plan_id,
                :client_quest_item_id,
                :task_id,
                :rank_order,
                :state,
                :reason_label,
                :reason,
                :action_label,
                :base_xp,
                :reward_xp,
                :focus_bonus_xp,
                :reward_multiplier,
                :has_focus_reward,
                :focus_target_minutes,
                :focus_seconds,
                :focus_minutes,
                TO_TIMESTAMP_TZ(:suggested_start_at, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
                TO_TIMESTAMP_TZ(:suggested_end_at, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
                NULL,
                NULL,
                NULL,
                NULL,
                SYSTIMESTAMP,
                SYSTIMESTAMP,
                1
            )
            """,
            {
                "quest_plan_id": quest_plan_id,
                "client_quest_item_id": quest.get("client_quest_item_id") or f"legacy-quest-{quest.get('task_id')}",
                "task_id": str(quest.get("task_id")),
                "rank_order": quest.get("rank_order"),
                "state": quest.get("state") or "QUEUED",
                "reason_label": quest.get("reason_label") or "",
                "reason": quest.get("reason") or "",
                "action_label": quest.get("action_label") or "",
                "base_xp": quest.get("base_xp") or quest.get("xp_value") or 0,
                "reward_xp": quest.get("reward_xp") or quest.get("xp_value") or 0,
                "focus_bonus_xp": quest.get("focus_bonus_xp") or 0,
                "reward_multiplier": quest.get("reward_multiplier") or 1,
                "has_focus_reward": 1 if quest.get("has_focus_reward") else 0,
                "focus_target_minutes": quest.get("focus_target_minutes") or 0,
                "focus_seconds": _focus_seconds(quest.get("focus_seconds"), quest.get("focus_minutes")),
                "focus_minutes": _focus_seconds(quest.get("focus_seconds"), quest.get("focus_minutes")) // 60,
                "suggested_start_at": quest.get("suggested_start_at"),
                "suggested_end_at": quest.get("suggested_end_at"),
            },
        )


def mark_quest_tasks_working(cur, user_id, quest_date, quests):
    for quest in quests:
        task_id = int(quest.get("task_id"))
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


def fetch_today_plan(cur, user_id, quest_date):
    plan = _fetch_plan_core(cur, user_id, quest_date)
    if not plan:
        return None
    plan["quests"] = _fetch_plan_items(cur, plan["quest_plan_id"])
    plan["id"] = plan.get("client_quest_run_id")
    plan["work_date"] = plan.get("quest_date")
    return plan


def create_or_replace_plan(cur, user_id, payload):
    _ensure_focus_seconds_columns(cur)
    focus_seconds = _focus_seconds(payload.get("focus_seconds"), payload.get("focus_minutes"))
    existing = _fetch_plan_core(cur, user_id, payload["quest_date"])
    if existing:
        quest_plan_id = existing["quest_plan_id"]
        cur.execute(
            """
            UPDATE QUEST_PLANS
            SET CLIENT_QUEST_RUN_ID = :client_quest_run_id,
                GENERATED_AT = :generated_at,
                SOURCE_TASK_IDS_JSON = :source_task_ids_json,
                ACTIVE_QUEST_ITEM_ID = NULL,
                STATUS = :status,
                CAPACITY_MINUTES = :capacity_minutes,
                MEETING_MINUTES = :meeting_minutes,
                FOCUS_SECONDS = :focus_seconds,
                FOCUS_MINUTES = :focus_minutes,
                SUMMARY = :summary,
                UPDATED_AT = SYSTIMESTAMP,
                ROW_VERSION = ROW_VERSION + 1
            WHERE USER_ID = :user_id
              AND QUEST_PLAN_ID = :quest_plan_id
            """,
            {
                "client_quest_run_id": payload["client_quest_run_id"],
                "generated_at": payload["generated_at"],
                "source_task_ids_json": json.dumps(payload.get("source_task_ids") or []),
                "status": payload["status"],
                "capacity_minutes": payload.get("capacity_minutes", 0),
                "meeting_minutes": payload.get("meeting_minutes", 0),
                "focus_seconds": focus_seconds,
                "focus_minutes": focus_seconds // 60,
                "summary": payload.get("summary") or "",
                "user_id": user_id,
                "quest_plan_id": quest_plan_id,
            },
        )
        existing_items = _fetch_plan_items(cur, quest_plan_id)
        existing_by_task_id = {str(item["task_id"]): item for item in existing_items}
    else:
        out_var = cur.var(int)
        cur.execute(
            """
            INSERT INTO QUEST_PLANS (
                QUEST_PLAN_ID,
                CLIENT_QUEST_RUN_ID,
                USER_ID,
                QUEST_DATE,
                GENERATED_AT,
                SOURCE_TASK_IDS_JSON,
                ACTIVE_QUEST_ITEM_ID,
                STATUS,
                CAPACITY_MINUTES,
                MEETING_MINUTES,
                FOCUS_SECONDS,
                FOCUS_MINUTES,
                SUMMARY,
                SOURCE_AI_RUN_ID,
                CREATED_AT,
                UPDATED_AT,
                ROW_VERSION
            )
            VALUES (
                QUEST_PLANS_SEQ.NEXTVAL,
                :client_quest_run_id,
                :user_id,
                TO_DATE(:quest_date, 'YYYY-MM-DD'),
                :generated_at,
                :source_task_ids_json,
                NULL,
                :status,
                :capacity_minutes,
                :meeting_minutes,
                :focus_seconds,
                :focus_minutes,
                :summary,
                NULL,
                SYSTIMESTAMP,
                SYSTIMESTAMP,
                1
            )
            RETURNING QUEST_PLAN_ID INTO :quest_plan_id
            """,
            {
                "client_quest_run_id": payload["client_quest_run_id"],
                "user_id": user_id,
                "quest_date": payload["quest_date"],
                "generated_at": payload["generated_at"],
                "source_task_ids_json": json.dumps(payload.get("source_task_ids") or []),
                "status": payload["status"],
                "capacity_minutes": payload.get("capacity_minutes", 0),
                "meeting_minutes": payload.get("meeting_minutes", 0),
                "focus_seconds": focus_seconds,
                "focus_minutes": focus_seconds // 60,
                "summary": payload.get("summary") or "",
                "quest_plan_id": out_var,
            },
        )
        quest_plan_id = _returned_id(out_var)
        existing_items = []
        existing_by_task_id = {}

    _prepare_existing_items_for_regeneration(cur, quest_plan_id, existing_items, payload.get("quests") or [])

    active_item_id = None
    seen_item_ids = set()
    for quest in payload.get("quests") or []:
        task_id = str(quest["task_id"])
        rank_order = quest.get("rank") or quest.get("rank_order") or 0
        existing_item = existing_by_task_id.get(task_id)
        if existing_item:
            inserted_item_id = existing_item["quest_item_id"]
            cur.execute(
                """
                UPDATE QUEST_ITEMS
                SET CLIENT_QUEST_ITEM_ID = :client_quest_item_id,
                    TASK_ID = :task_id,
                    RANK_ORDER = :rank_order,
                    STATE = :state,
                    REASON_LABEL = :reason_label,
                    REASON = :reason,
                    ACTION_LABEL = :action_label,
                    BASE_XP = :base_xp,
                    REWARD_XP = :reward_xp,
                    FOCUS_BONUS_XP = :focus_bonus_xp,
                    REWARD_MULTIPLIER = :reward_multiplier,
                    HAS_FOCUS_REWARD = :has_focus_reward,
                    FOCUS_TARGET_MINUTES = :focus_target_minutes,
                    FOCUS_SECONDS = :focus_seconds,
                    FOCUS_MINUTES = :focus_minutes,
                    SUGGESTED_START_AT = :suggested_start_at,
                    SUGGESTED_END_AT = :suggested_end_at,
                    STARTED_AT = :started_at,
                    COMPLETED_AT = :completed_at,
                    SKIPPED_AT = :skipped_at,
                    SKIP_REASON = :skip_reason,
                    UPDATED_AT = SYSTIMESTAMP,
                    ROW_VERSION = ROW_VERSION + 1
                WHERE QUEST_ITEM_ID = :quest_item_id
                """,
                {
                    "client_quest_item_id": quest["id"],
                    "task_id": task_id,
                    "rank_order": rank_order,
                    "state": quest["state"],
                    "reason_label": quest.get("reason_label") or "",
                    "reason": quest.get("reason") or "",
                    "action_label": quest.get("action_label") or "",
                    "base_xp": quest.get("base_xp") or 0,
                    "reward_xp": quest.get("reward_xp") or 0,
                    "focus_bonus_xp": quest.get("focus_bonus_xp") or 0,
                    "reward_multiplier": quest.get("reward_multiplier") or 1,
                    "has_focus_reward": 1 if quest.get("has_focus_reward") else 0,
                    "focus_target_minutes": quest.get("focus_target_minutes") or 0,
                    "focus_seconds": _focus_seconds(quest.get("focus_seconds"), quest.get("focus_minutes")),
                    "focus_minutes": _focus_seconds(quest.get("focus_seconds"), quest.get("focus_minutes")) // 60,
                    "suggested_start_at": quest.get("suggested_start_at"),
                    "suggested_end_at": quest.get("suggested_end_at"),
                    "started_at": quest.get("started_at"),
                    "completed_at": quest.get("completed_at"),
                    "skipped_at": quest.get("skipped_at"),
                    "skip_reason": quest.get("skip_reason"),
                    "quest_item_id": inserted_item_id,
                },
            )
        else:
            item_out = cur.var(int)
            cur.execute(
                """
                INSERT INTO QUEST_ITEMS (
                    QUEST_ITEM_ID,
                    QUEST_PLAN_ID,
                    CLIENT_QUEST_ITEM_ID,
                    TASK_ID,
                    RANK_ORDER,
                    STATE,
                    REASON_LABEL,
                    REASON,
                    ACTION_LABEL,
                    BASE_XP,
                    REWARD_XP,
                    FOCUS_BONUS_XP,
                    REWARD_MULTIPLIER,
                    HAS_FOCUS_REWARD,
                    FOCUS_TARGET_MINUTES,
                    FOCUS_SECONDS,
                    FOCUS_MINUTES,
                    SUGGESTED_START_AT,
                    SUGGESTED_END_AT,
                    STARTED_AT,
                    COMPLETED_AT,
                    SKIPPED_AT,
                    SKIP_REASON,
                    CREATED_AT,
                    UPDATED_AT,
                    ROW_VERSION
                )
                VALUES (
                    QUEST_ITEMS_SEQ.NEXTVAL,
                    :quest_plan_id,
                    :client_quest_item_id,
                    :task_id,
                    :rank_order,
                    :state,
                    :reason_label,
                    :reason,
                    :action_label,
                    :base_xp,
                    :reward_xp,
                    :focus_bonus_xp,
                    :reward_multiplier,
                    :has_focus_reward,
                    :focus_target_minutes,
                    :focus_seconds,
                    :focus_minutes,
                    :suggested_start_at,
                    :suggested_end_at,
                    :started_at,
                    :completed_at,
                    :skipped_at,
                    :skip_reason,
                    SYSTIMESTAMP,
                    SYSTIMESTAMP,
                    1
                )
                RETURNING QUEST_ITEM_ID INTO :quest_item_id
                """,
                {
                    "quest_plan_id": quest_plan_id,
                    "client_quest_item_id": quest["id"],
                    "task_id": task_id,
                    "rank_order": rank_order,
                    "state": quest["state"],
                    "reason_label": quest.get("reason_label") or "",
                    "reason": quest.get("reason") or "",
                    "action_label": quest.get("action_label") or "",
                    "base_xp": quest.get("base_xp") or 0,
                    "reward_xp": quest.get("reward_xp") or 0,
                    "focus_bonus_xp": quest.get("focus_bonus_xp") or 0,
                    "reward_multiplier": quest.get("reward_multiplier") or 1,
                    "has_focus_reward": 1 if quest.get("has_focus_reward") else 0,
                    "focus_target_minutes": quest.get("focus_target_minutes") or 0,
                    "focus_seconds": _focus_seconds(quest.get("focus_seconds"), quest.get("focus_minutes")),
                    "focus_minutes": _focus_seconds(quest.get("focus_seconds"), quest.get("focus_minutes")) // 60,
                    "suggested_start_at": quest.get("suggested_start_at"),
                    "suggested_end_at": quest.get("suggested_end_at"),
                    "started_at": quest.get("started_at"),
                    "completed_at": quest.get("completed_at"),
                    "skipped_at": quest.get("skipped_at"),
                    "skip_reason": quest.get("skip_reason"),
                    "quest_item_id": item_out,
                },
            )
            inserted_item_id = _returned_id(item_out)
        seen_item_ids.add(inserted_item_id)
        if str(quest.get("state") or "").upper() == "ACTIVE":
            active_item_id = inserted_item_id

    for item in existing_items:
        if item["quest_item_id"] in seen_item_ids:
            continue
        cur.execute(
            """
            UPDATE QUEST_ITEMS
            SET STATE = 'SKIPPED',
                SKIPPED_AT = COALESCE(SKIPPED_AT, SYSTIMESTAMP),
                SKIP_REASON = COALESCE(SKIP_REASON, 'Not today'),
                UPDATED_AT = SYSTIMESTAMP,
                ROW_VERSION = ROW_VERSION + 1
            WHERE QUEST_ITEM_ID = :quest_item_id
            """,
            {"quest_item_id": item["quest_item_id"]},
        )

    cur.execute(
        """
        UPDATE QUEST_PLANS
        SET ACTIVE_QUEST_ITEM_ID = :active_quest_item_id,
            STATUS = :status,
            UPDATED_AT = SYSTIMESTAMP,
            ROW_VERSION = ROW_VERSION + 1
        WHERE QUEST_PLAN_ID = :quest_plan_id
        """,
        {
            "active_quest_item_id": active_item_id,
            "status": "ACTIVE" if active_item_id else payload["status"],
            "quest_plan_id": quest_plan_id,
        },
    )
    return fetch_today_plan(cur, user_id, payload["quest_date"])


def fetch_item_with_plan(cur, user_id, quest_item_id):
    cur.execute(
        """
        SELECT
            qi.QUEST_ITEM_ID,
            qi.QUEST_PLAN_ID,
            qi.CLIENT_QUEST_ITEM_ID,
            qi.TASK_ID,
            qp.USER_ID,
            TO_CHAR(qp.QUEST_DATE, 'YYYY-MM-DD')
        FROM QUEST_ITEMS qi
        JOIN QUEST_PLANS qp
          ON qp.QUEST_PLAN_ID = qi.QUEST_PLAN_ID
        WHERE qp.USER_ID = :user_id
          AND qi.QUEST_ITEM_ID = :quest_item_id
        """,
        {"user_id": user_id, "quest_item_id": quest_item_id},
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "quest_item_id": int(row[0]),
        "quest_plan_id": int(row[1]),
        "client_quest_item_id": row[2],
        "task_id": int(row[3]),
        "user_id": int(row[4]),
        "quest_date": row[5],
    }


def list_completed_quest_dates(cur, user_id, reference_date):
    cur.execute(
        """
        SELECT DISTINCT TO_CHAR(qp.QUEST_DATE, 'YYYY-MM-DD')
        FROM QUEST_ITEMS qi
        JOIN QUEST_PLANS qp
          ON qp.QUEST_PLAN_ID = qi.QUEST_PLAN_ID
        WHERE qp.USER_ID = :user_id
          AND qi.STATE = 'COMPLETED'
          AND qp.QUEST_DATE <= TO_DATE(:reference_date, 'YYYY-MM-DD')
        ORDER BY TO_CHAR(qp.QUEST_DATE, 'YYYY-MM-DD')
        """,
        {"user_id": user_id, "reference_date": reference_date},
    )
    return [row[0] for row in cur.fetchall() if row and row[0]]


def count_completed_quests(cur, user_id, reference_date):
    cur.execute(
        """
        SELECT COUNT(*)
        FROM QUEST_ITEMS qi
        JOIN QUEST_PLANS qp
          ON qp.QUEST_PLAN_ID = qi.QUEST_PLAN_ID
        WHERE qp.USER_ID = :user_id
          AND qi.STATE = 'COMPLETED'
          AND qp.QUEST_DATE <= TO_DATE(:reference_date, 'YYYY-MM-DD')
        """,
        {"user_id": user_id, "reference_date": reference_date},
    )
    row = cur.fetchone()
    return int(row[0] or 0) if row else 0


def resolve_client_item_id(cur, user_id, client_quest_item_id):
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


def update_active_item(cur, quest_plan_id, quest_item_id, now):
    cur.execute(
        """
        UPDATE QUEST_ITEMS
        SET STATE = CASE
            WHEN QUEST_ITEM_ID = :quest_item_id THEN 'ACTIVE'
            WHEN STATE IN ('ACTIVE', 'QUEUED') THEN 'QUEUED'
            ELSE STATE
        END,
            STARTED_AT = CASE
                WHEN QUEST_ITEM_ID = :quest_item_id AND STARTED_AT IS NULL THEN :now
                ELSE STARTED_AT
            END,
            UPDATED_AT = SYSTIMESTAMP,
            ROW_VERSION = ROW_VERSION + 1
        WHERE QUEST_PLAN_ID = :quest_plan_id
        """,
        {"quest_plan_id": quest_plan_id, "quest_item_id": quest_item_id, "now": now},
    )
    cur.execute(
        """
        UPDATE QUEST_PLANS
        SET ACTIVE_QUEST_ITEM_ID = :quest_item_id,
            STATUS = 'ACTIVE',
            UPDATED_AT = SYSTIMESTAMP,
            ROW_VERSION = ROW_VERSION + 1
        WHERE QUEST_PLAN_ID = :quest_plan_id
        """,
        {"quest_plan_id": quest_plan_id, "quest_item_id": quest_item_id},
    )


def skip_item(cur, quest_plan_id, quest_item_id, skip_reason, now):
    cur.execute(
        """
        UPDATE QUEST_ITEMS
        SET STATE = 'SKIPPED',
            SKIPPED_AT = :now,
            SKIP_REASON = :skip_reason,
            UPDATED_AT = SYSTIMESTAMP,
            ROW_VERSION = ROW_VERSION + 1
        WHERE QUEST_PLAN_ID = :quest_plan_id
          AND QUEST_ITEM_ID = :quest_item_id
        """,
        {"quest_plan_id": quest_plan_id, "quest_item_id": quest_item_id, "skip_reason": skip_reason, "now": now},
    )
    _refresh_active_item(cur, quest_plan_id)


def complete_item(cur, quest_plan_id, quest_item_id, now):
    cur.execute(
        """
        UPDATE QUEST_ITEMS
        SET STATE = 'COMPLETED',
            COMPLETED_AT = :now,
            UPDATED_AT = SYSTIMESTAMP,
            ROW_VERSION = ROW_VERSION + 1
        WHERE QUEST_PLAN_ID = :quest_plan_id
          AND QUEST_ITEM_ID = :quest_item_id
        """,
        {"quest_plan_id": quest_plan_id, "quest_item_id": quest_item_id, "now": now},
    )
    _refresh_active_item(cur, quest_plan_id)


def _refresh_active_item(cur, quest_plan_id):
    cur.execute(
        """
        SELECT QUEST_ITEM_ID
        FROM QUEST_ITEMS
        WHERE QUEST_PLAN_ID = :quest_plan_id
          AND STATE IN ('ACTIVE', 'QUEUED')
        ORDER BY RANK_ORDER, QUEST_ITEM_ID
        FETCH FIRST 1 ROWS ONLY
        """,
        {"quest_plan_id": quest_plan_id},
    )
    row = cur.fetchone()
    next_item_id = int(row[0]) if row else None
    if next_item_id is not None:
        cur.execute(
            """
            UPDATE QUEST_ITEMS
            SET STATE = CASE
                WHEN QUEST_ITEM_ID = :quest_item_id THEN 'ACTIVE'
                WHEN STATE IN ('ACTIVE', 'QUEUED') THEN 'QUEUED'
                ELSE STATE
            END,
                UPDATED_AT = SYSTIMESTAMP,
                ROW_VERSION = ROW_VERSION + 1
            WHERE QUEST_PLAN_ID = :quest_plan_id
            """,
            {"quest_plan_id": quest_plan_id, "quest_item_id": next_item_id},
        )
    cur.execute(
        """
        UPDATE QUEST_PLANS
        SET ACTIVE_QUEST_ITEM_ID = :active_quest_item_id,
            STATUS = :status,
            UPDATED_AT = SYSTIMESTAMP,
            ROW_VERSION = ROW_VERSION + 1
        WHERE QUEST_PLAN_ID = :quest_plan_id
        """,
        {
            "quest_plan_id": quest_plan_id,
            "active_quest_item_id": next_item_id,
            "status": "ACTIVE" if next_item_id is not None else "COMPLETED",
        },
    )


def _fetch_plan_core(cur, user_id, quest_date):
    _ensure_focus_seconds_columns(cur)
    cur.execute(
        """
        SELECT
            QUEST_PLAN_ID,
            CLIENT_QUEST_RUN_ID,
            TO_CHAR(QUEST_DATE, 'YYYY-MM-DD'),
            TO_CHAR(GENERATED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            SOURCE_TASK_IDS_JSON,
            ACTIVE_QUEST_ITEM_ID,
            STATUS,
            CAPACITY_MINUTES,
            MEETING_MINUTES,
            FOCUS_SECONDS,
            FOCUS_MINUTES,
            SUMMARY,
            SOURCE_AI_RUN_ID,
            TO_CHAR(CREATED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            TO_CHAR(UPDATED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            ROW_VERSION
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
        "quest_plan_id": int(row[0]),
        "client_quest_run_id": row[1],
        "quest_date": row[2],
        "generated_at": row[3],
        "source_task_ids": _json_loads(row[4]),
        "active_quest_item_id": int(row[5]) if row[5] is not None else None,
        "status": row[6],
        "capacity_minutes": int(row[7] or 0),
        "meeting_minutes": int(row[8] or 0),
        "focus_seconds": _focus_seconds(row[9], row[10]),
        "focus_minutes": int(row[10] or 0),
        "summary": _text(row[11]),
        "source_ai_run_id": row[12],
        "created_at": row[13],
        "updated_at": row[14],
        "row_version": int(row[15] or 1),
    }


def _fetch_plan_items(cur, quest_plan_id):
    _ensure_focus_seconds_columns(cur)
    cur.execute(
        """
        SELECT
            QUEST_ITEM_ID,
            CLIENT_QUEST_ITEM_ID,
            TASK_ID,
            RANK_ORDER,
            STATE,
            REASON_LABEL,
            REASON,
            ACTION_LABEL,
            BASE_XP,
            REWARD_XP,
            FOCUS_BONUS_XP,
            REWARD_MULTIPLIER,
            HAS_FOCUS_REWARD,
            FOCUS_TARGET_MINUTES,
            FOCUS_SECONDS,
            FOCUS_MINUTES,
            TO_CHAR(SUGGESTED_START_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            TO_CHAR(SUGGESTED_END_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            TO_CHAR(STARTED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            TO_CHAR(COMPLETED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            TO_CHAR(SKIPPED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            SKIP_REASON,
            TO_CHAR(CREATED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            TO_CHAR(UPDATED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            ROW_VERSION
        FROM QUEST_ITEMS
        WHERE QUEST_PLAN_ID = :quest_plan_id
        ORDER BY RANK_ORDER, QUEST_ITEM_ID
        """,
        {"quest_plan_id": quest_plan_id},
    )
    items = []
    for row in cur.fetchall():
        items.append(
            {
                "quest_item_id": int(row[0]),
                "id": row[1],
                "client_quest_item_id": row[1],
                "task_id": row[2],
                "rank": int(row[3] or 0),
                "rank_order": int(row[3] or 0),
                "state": row[4],
                "reason_label": row[5] or "",
                "reason": _text(row[6]),
                "action_label": row[7] or "",
                "base_xp": int(row[8] or 0),
                "reward_xp": int(row[9] or 0),
                "focus_bonus_xp": int(row[10] or 0),
                "reward_multiplier": float(row[11] or 1),
                "has_focus_reward": bool(row[12]),
                "focus_target_minutes": int(row[13] or 0),
                "focus_seconds": _focus_seconds(row[14], row[15]),
                "focus_minutes": int(row[15] or 0),
                "suggested_start_at": row[16],
                "suggested_end_at": row[17],
                "started_at": row[18],
                "completed_at": row[19],
                "skipped_at": row[20],
                "skip_reason": row[21] or "",
                "created_at": row[22],
                "updated_at": row[23],
                "row_version": int(row[24] or 1),
            }
        )
    return items


def _referenced_quest_item_ids(cur, quest_plan_id):
    cur.execute(
        """
        SELECT DISTINCT fs.QUEST_ITEM_ID
        FROM FOCUS_SESSIONS fs
        JOIN QUEST_ITEMS qi
          ON qi.QUEST_ITEM_ID = fs.QUEST_ITEM_ID
        WHERE qi.QUEST_PLAN_ID = :quest_plan_id
          AND fs.QUEST_ITEM_ID IS NOT NULL
        """,
        {"quest_plan_id": quest_plan_id},
    )
    return {int(row[0]) for row in cur.fetchall()}


def _prepare_existing_items_for_regeneration(cur, quest_plan_id, existing_items, incoming_quests):
    if not existing_items:
        return

    highest_live_rank = max(
        [int(quest.get("rank") or quest.get("rank_order") or 0) for quest in incoming_quests]
        + [int(item.get("rank") or item.get("rank_order") or 0) for item in existing_items]
        + [0]
    )
    next_rank_order = highest_live_rank + 1000

    for item in existing_items:
        cur.execute(
            """
            UPDATE QUEST_ITEMS
            SET RANK_ORDER = :rank_order,
                UPDATED_AT = SYSTIMESTAMP,
                ROW_VERSION = ROW_VERSION + 1
            WHERE QUEST_ITEM_ID = :quest_item_id
            """,
            {"quest_item_id": item["quest_item_id"], "rank_order": next_rank_order},
        )
        item["rank_order"] = next_rank_order
        item["rank"] = next_rank_order
        next_rank_order += 1

    incoming_task_ids = {str(quest.get("task_id")) for quest in incoming_quests}
    referenced_item_ids = _referenced_quest_item_ids(cur, quest_plan_id)

    for item in existing_items:
        if str(item.get("task_id")) in incoming_task_ids:
            continue
        if item["quest_item_id"] in referenced_item_ids:
            cur.execute(
                """
                UPDATE QUEST_ITEMS
                SET STATE = 'SKIPPED',
                    SKIPPED_AT = SYSTIMESTAMP,
                    SKIP_REASON = 'Not today',
                    UPDATED_AT = SYSTIMESTAMP,
                    ROW_VERSION = ROW_VERSION + 1
                WHERE QUEST_ITEM_ID = :quest_item_id
                """,
                {"quest_item_id": item["quest_item_id"]},
            )
        else:
            cur.execute("DELETE FROM QUEST_ITEMS WHERE QUEST_ITEM_ID = :quest_item_id", {"quest_item_id": item["quest_item_id"]})


def _returned_id(var):
    value = var.getvalue()
    return value[0] if isinstance(value, list) else value


def _text(value):
    if value is None:
        return ""
    if hasattr(value, "read"):
        return value.read()
    return str(value)


def _json_loads(value):
    text = _text(value).strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _ensure_focus_seconds_columns(cur):
    for table_name in ("QUEST_PLANS", "QUEST_ITEMS"):
        if not _column_exists(cur, table_name, "FOCUS_SECONDS"):
            cur.execute(f"ALTER TABLE {table_name} ADD FOCUS_SECONDS NUMBER(19)")


def _column_exists(cur, table_name, column_name):
    cur.execute(
        """
        SELECT COUNT(*)
        FROM USER_TAB_COLS
        WHERE TABLE_NAME = :table_name
          AND COLUMN_NAME = :column_name
        """,
        {"table_name": table_name.upper(), "column_name": column_name.upper()},
    )
    return bool(cur.fetchone()[0])
