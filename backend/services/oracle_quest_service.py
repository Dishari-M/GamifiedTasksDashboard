from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

import oracledb
from fastapi import HTTPException

from db import get_connection
from repositories import quest_repository, task_repository
from services.phase8_capacity_service import build_capacity


SKIP_REASONS = {"Blocked", "Not today", "Too large"}
PRIORITY_RANK = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
STATUS_RANK = {"In Progress": 4, "To Do": 3, "Blocked": 2, "Upcoming": 1, "Done": 0}
PLAN_STATUS_NOT_GENERATED = "NOT_GENERATED"
PLAN_STATUS_ACTIVE = "ACTIVE"
ITEM_STATE_ACTIVE = "ACTIVE"
ITEM_STATE_QUEUED = "QUEUED"
logger = logging.getLogger(__name__)


def oracle_quests_today_response(date, user_id=1):
    quest_date = _resolve_date(date)
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        plan = quest_repository.fetch_today_plan(cur, int(user_id), quest_date)
        if plan:
            return {"data": _frontend_quest_run(plan), "meta": {"request_id": str(uuid4())}}
        tasks = _candidate_tasks(cur, int(user_id), quest_date)
        return {"data": _build_ephemeral_run(tasks, quest_date), "meta": {"request_id": str(uuid4())}}
    except oracledb.DatabaseError as exc:
        raise HTTPException(status_code=503, detail="Quest storage is unavailable.") from exc
    finally:
        if conn:
            conn.close()


def oracle_generate_quests_response(payload, user_id=1):
    quest_date = _resolve_date(payload.quest_date)
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        tasks = _candidate_tasks(cur, int(user_id), quest_date)
        candidate_ids = {str(value) for value in (payload.candidate_task_ids or [])}
        if candidate_ids:
            tasks = [task for task in tasks if str(task["task_id"]) in candidate_ids or str(task["id"]) in candidate_ids]
        tasks = tasks[: max(1, min(int(payload.max_quests), 10))]
        plan = _create_plan(cur, int(user_id), quest_date, tasks)
        conn.commit()
        return {"data": _frontend_quest_run(plan), "meta": {"request_id": str(uuid4())}}
    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except oracledb.DatabaseError as exc:
        if conn:
            conn.rollback()
        logger.exception("Oracle quest generation failed for user_id=%s quest_date=%s payload=%s", user_id, quest_date, payload.model_dump())
        raise HTTPException(status_code=503, detail="Quest storage is unavailable.") from exc
    finally:
        if conn:
            conn.close()


def oracle_update_quest_response(quest_item_id, payload, user_id=1):
    data = dict(payload or {})
    action = str(data.get("action") or "").strip().lower()
    if action not in {"activate", "skip", "complete"}:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "action must be activate, skip, or complete.", "details": {"field": "action"}})
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        resolved_id = _resolve_quest_item_id(cur, int(user_id), quest_item_id)
        item = quest_repository.fetch_item_with_plan(cur, int(user_id), resolved_id)
        if not item:
            raise HTTPException(status_code=404, detail={"code": "QUEST_NOT_FOUND", "message": "Quest item was not found."})
        now = datetime.now(UTC)
        if action == "activate":
            quest_repository.update_active_item(cur, item["quest_plan_id"], item["quest_item_id"], now)
        elif action == "skip":
            skip_reason = str(data.get("skip_reason") or data.get("skipReason") or "").strip()
            if skip_reason not in SKIP_REASONS:
                raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "Invalid skip reason.", "details": {"field": "skip_reason", "allowed": sorted(SKIP_REASONS)}})
            quest_repository.skip_item(cur, item["quest_plan_id"], item["quest_item_id"], skip_reason, now)
        elif action == "complete":
            _complete_task_for_quest(cur, int(user_id), item["task_id"], now)
            quest_repository.complete_item(cur, item["quest_plan_id"], item["quest_item_id"], now)
        plan = quest_repository.fetch_today_plan(cur, int(user_id), item["quest_date"])
        conn.commit()
        return {"data": _frontend_quest_run(plan), "meta": {"request_id": str(uuid4())}}
    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except oracledb.DatabaseError as exc:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=503, detail="Quest storage is unavailable.") from exc
    finally:
        if conn:
            conn.close()


def _candidate_tasks(cur, user_id, quest_date):
    listing = task_repository.list_tasks(
        cur,
        user_id,
        {"working_today": True, "page": 1, "page_size": 100},
        quest_date,
    )
    return sorted(listing["items"], key=_task_rank)


def _task_rank(task):
    return (
        -(STATUS_RANK.get(task.get("status"), 0)),
        -float(task.get("priorityScore") or 0),
        -(PRIORITY_RANK.get(task.get("priority"), 0)),
        -float(task.get("impact") or 0),
        int(task.get("time") or 0),
    )


def _create_plan(cur, user_id, quest_date, tasks):
    capacity = build_capacity(quest_date)
    client_run_id = f"quest-run-{quest_date}-{int(datetime.now(UTC).timestamp() * 1000)}"
    quests = []
    for index, task in enumerate(tasks, start=1):
        focus_target = _focus_target_minutes(task)
        state = ITEM_STATE_ACTIVE if index == 1 else ITEM_STATE_QUEUED
        quests.append(
            {
                "id": f"quest-{task['id']}",
                "task_id": task["id"],
                "rank": index,
                "state": state,
                "reason_label": _reason_label(task, index),
                "reason": _reason(task, index),
                "action_label": _action_label(task),
                "base_xp": int(task.get("xp") or 0),
                "reward_xp": int(task.get("xp") or 0),
                "focus_bonus_xp": 0,
                "reward_multiplier": 1,
                "has_focus_reward": False,
                "focus_target_minutes": focus_target,
                "focus_minutes": 0,
                "suggested_start_at": None,
                "suggested_end_at": None,
                "started_at": datetime.now(UTC) if index == 1 else None,
                "completed_at": None,
                "skipped_at": None,
                "skip_reason": None,
            }
        )
    payload = {
        "client_quest_run_id": client_run_id,
        "quest_date": quest_date,
        "generated_at": datetime.now(UTC),
        "source_task_ids": [str(task["id"]) for task in tasks],
        "status": PLAN_STATUS_ACTIVE if quests else PLAN_STATUS_NOT_GENERATED,
        "capacity_minutes": capacity.get("available_focus_minutes", 0),
        "meeting_minutes": capacity.get("meeting_minutes", 0),
        "focus_minutes": 0,
        "summary": f"Generated from {len(tasks)} Working Today task{'s' if len(tasks) != 1 else ''}." if tasks else "Mark tasks as Working Today to generate quests.",
        "quests": quests,
    }
    return quest_repository.create_or_replace_plan(cur, user_id, payload)


def _build_ephemeral_run(tasks, quest_date):
    return _frontend_quest_run(
        {
            "id": f"quest-run-{quest_date}-preview",
            "client_quest_run_id": f"quest-run-{quest_date}-preview",
            "quest_plan_id": None,
            "work_date": quest_date,
            "generated_at": None,
            "source_task_ids": [str(task["id"]) for task in tasks],
            "status": PLAN_STATUS_NOT_GENERATED,
            "summary": "Working Today tasks are ready for quest generation." if tasks else "Mark tasks as Working Today to generate quests.",
            "quests": [
                {
                    "quest_item_id": None,
                    "id": f"quest-{task['id']}",
                    "client_quest_item_id": f"quest-{task['id']}",
                    "task_id": str(task["id"]),
                    "rank": index,
                    "rank_order": index,
                    "state": ITEM_STATE_ACTIVE if index == 1 else ITEM_STATE_QUEUED,
                    "reason_label": _reason_label(task, index),
                    "reason": _reason(task, index),
                    "action_label": _action_label(task),
                    "base_xp": int(task.get("xp") or 0),
                    "reward_xp": int(task.get("xp") or 0),
                    "focus_bonus_xp": 0,
                    "reward_multiplier": 1,
                    "has_focus_reward": False,
                    "focus_target_minutes": _focus_target_minutes(task),
                    "focus_minutes": 0,
                    "started_at": None,
                    "completed_at": None,
                    "skipped_at": None,
                    "skip_reason": "",
                }
                for index, task in enumerate(tasks, start=1)
            ],
        }
    )


def _frontend_quest_run(plan):
    quests = []
    active_id = None
    for item in plan.get("quests", []):
        quest_id = item.get("id") or item.get("client_quest_item_id")
        if _frontend_state(item.get("state")) == "active":
            active_id = quest_id
        quests.append(
            {
                "quest_item_id": item.get("quest_item_id"),
                "id": quest_id,
                "taskId": str(item.get("task_id")),
                "rank": item.get("rank") or item.get("rank_order"),
                "state": _frontend_state(item.get("state")),
                "reason": item.get("reason") or "",
                "reasonLabel": item.get("reason_label") or "",
                "actionLabel": item.get("action_label") or "",
                "baseXp": item.get("base_xp") or 0,
                "rewardXp": item.get("reward_xp") or 0,
                "focusBonusXp": item.get("focus_bonus_xp") or 0,
                "rewardMultiplier": item.get("reward_multiplier") or 1,
                "hasFocusReward": bool(item.get("has_focus_reward")),
                "focusTargetMinutes": item.get("focus_target_minutes") or 0,
                "focusMinutes": item.get("focus_minutes") or 0,
                "startedAt": item.get("started_at"),
                "completedAt": item.get("completed_at"),
                "skippedAt": item.get("skipped_at"),
                "skipReason": item.get("skip_reason") or "",
            }
        )
    return {
        "quest_plan_id": plan.get("quest_plan_id"),
        "id": plan.get("id") or plan.get("client_quest_run_id"),
        "workDate": plan.get("work_date"),
        "generatedAt": plan.get("generated_at"),
        "sourceTaskIds": plan.get("source_task_ids") or [],
        "activeQuestId": active_id,
        "status": _frontend_plan_status(plan.get("status")) or ("active" if quests else "not_generated"),
        "summary": plan.get("summary") or "",
        "quests": quests,
    }


def _reason_label(task, index):
    if task.get("status") == "Blocked":
        return "Unblock first"
    if task.get("status") == "In Progress":
        return "Continue"
    if str(task.get("dueDate") or "") == _resolve_date(None):
        return "Scheduled"
    if int(task.get("time") or 0) <= 35:
        return "Quick win"
    if task.get("priority") in {"Critical", "High"} or float(task.get("impact") or 0) >= 8:
        return "High impact"
    return "Best next" if index == 1 else "Steady progress"


def _reason(task, index):
    label = _reason_label(task, index)
    if label == "Unblock first":
        return "Unblock first: Clear the dependency before adding more work on top."
    if label == "Continue":
        return "Continue: This is already open, so finishing the thread protects momentum."
    if label == "Scheduled":
        return "Scheduled: It is tied to today, so it should stay visible in the route."
    if label == "Quick win":
        return "Quick win: Small enough to complete cleanly and bank progress."
    if label == "High impact":
        return "High impact: High priority and impact make it worth doing before lower leverage work."
    return f"{label}: {task.get('priority')} priority {str(task.get('type') or 'Task').lower()} from {task.get('source')}, estimated at {int(task.get('time') or 0)} mins."


def _action_label(task):
    if task.get("status") == "Done":
        return "Completed"
    if task.get("status") == "Blocked":
        return "Resolve blocker"
    if task.get("status") == "In Progress":
        return "Continue"
    if task.get("status") == "Upcoming":
        return "Prepare"
    return "Start"


def _focus_target_minutes(task):
    effort = max(25, int(task.get("time") or 60))
    if effort <= 30:
        return effort
    return min(90, max(25, ((effort * 55 + 99) // 100 + 4) // 5 * 5))


def _complete_task_for_quest(cur, user_id, task_id, completed_at):
    task_numeric_id = int(task_id)
    existing = task_repository.fetch_task_for_update(cur, user_id, task_numeric_id)
    if not existing:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "Task was not found."})
    task_repository.update_task_fields(
        cur,
        user_id,
        task_numeric_id,
        [("STATUS", "status", "Done"), ("COMPLETED_AT", "completed_at", completed_at)],
        existing["row_version"],
    )
    task_repository.delete_work_date(cur, user_id, task_numeric_id, _resolve_date(None))
    task_repository.insert_task_event(
        cur,
        user_id,
        task_numeric_id,
        "TASK_COMPLETED",
        {"row_version": existing["row_version"]},
        {"status": "Done", "completed_at": completed_at.isoformat()},
    )


def _resolve_quest_item_id(cur, user_id, quest_item_id):
    text = str(quest_item_id or "").strip()
    if text.isdigit():
        return int(text)
    resolved = quest_repository.resolve_client_item_id(cur, user_id, text)
    if resolved is None:
        raise HTTPException(status_code=404, detail={"code": "QUEST_NOT_FOUND", "message": "Quest item was not found."})
    return resolved


def _resolve_date(value):
    if not value:
        return datetime.now(UTC).date().isoformat()
    return str(value).strip()


def _frontend_state(value):
    text = str(value or "").strip().upper()
    return {
        "ACTIVE": "active",
        "QUEUED": "queued",
        "COMPLETED": "completed",
        "SKIPPED": "skipped",
    }.get(text, text.lower())


def _frontend_plan_status(value):
    text = str(value or "").strip().upper()
    return {
        "NOT_GENERATED": "not_generated",
        "ACTIVE": "active",
        "NEEDS_UPDATE": "needs_update",
        "COMPLETED": "completed",
    }.get(text, text.lower())
