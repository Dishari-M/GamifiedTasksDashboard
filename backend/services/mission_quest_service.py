from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException

from config import get_oci_genai_model_id
from services.filesystem_store import read_records, with_store_lock, write_records
from services.mission_quest_ai_service import (
    MISSION_SYSTEM_PROMPT,
    QUEST_SYSTEM_PROMPT,
    build_mission_ai_output,
    build_quest_ai_output,
)
from services.phase8_capacity_service import build_capacity
from services.phase8_data_provider import get_calendar_events, resolve_work_date
from services.xp_service import resolve_xp_value


WORK_ITEMS_FILE = "work_items.json"
DAILY_WORK_ITEMS_FILE = "daily_work_items.json"
AI_RUNS_FILE = "ai_runs.json"
QUEST_PLANS_FILE = "quest_plans.json"
QUEST_ITEMS_FILE = "quest_items.json"


def missions_generate_response(payload, user_id):
    work_date = resolve_work_date(payload.date)
    return {
        "data": generate_missions(work_date, payload.model_dump(), user_id),
        "meta": {"request_id": str(uuid4())},
    }


def quests_today_response(date, user_id):
    quest_date = resolve_work_date(date)
    return {
        "data": get_quests_today(quest_date, user_id),
        "meta": {"request_id": str(uuid4())},
    }


def quests_generate_response(payload, user_id):
    quest_date = resolve_work_date(payload.quest_date)
    return {
        "data": generate_quests(quest_date, payload.model_dump(), user_id),
        "meta": {"request_id": str(uuid4())},
    }


def generate_missions(work_date, request_payload, user_id):
    def action():
        tasks = _candidate_tasks(read_records(WORK_ITEMS_FILE), user_id, work_date, request_payload)
        context = _context(work_date, tasks, request_payload, "missions")
        ai_runs = read_records(AI_RUNS_FILE)
        ai_run = _create_ai_run(ai_runs, user_id, "MISSION_RECOMMENDATIONS", work_date, MISSION_SYSTEM_PROMPT, context, request_payload)
        write_records(AI_RUNS_FILE, ai_runs)
        try:
            ai = build_mission_ai_output(context)
            missions = _validated_missions(ai.get("missions") or [], tasks, request_payload.get("max_missions", 5))
            ai = {**ai, "missions": missions}
        except Exception as exc:
            _mark_ai_run_failed(ai_runs, ai_run["ai_run_id"], exc)
            write_records(AI_RUNS_FILE, ai_runs)
            raise
        _mark_ai_run_succeeded(ai_runs, ai_run["ai_run_id"], ai)
        write_records(AI_RUNS_FILE, ai_runs)
        return {
            "date": work_date,
            "summary": ai.get("summary") or "",
            "missions": missions,
            "ai_run_id": ai_run["ai_run_id"],
            "generated_at": ai.get("generated_at"),
        }

    return with_store_lock(action)


def get_quests_today(quest_date, user_id):
    def action():
        tasks = _candidate_tasks(
            read_records(WORK_ITEMS_FILE),
            user_id,
            quest_date,
            {"respect_working_today": True, "max_quests": 10},
        )
        capacity = build_capacity(quest_date)
        plans = read_records(QUEST_PLANS_FILE)
        items = read_records(QUEST_ITEMS_FILE)
        plan = _latest_plan(plans, user_id, quest_date)
        if plan:
            plan_items = sorted(
                [item for item in items if item.get("quest_plan_id") == plan.get("quest_plan_id")],
                key=lambda item: item.get("rank_order") or 999,
            )
            task_by_id = {task["task_id"]: task for task in _user_tasks(read_records(WORK_ITEMS_FILE), user_id)}
            return {
                "quest_plan_id": plan.get("quest_plan_id"),
                "quest_date": quest_date,
                "source": "QUEST_PLANS",
                "capacity": _capacity_response(capacity),
                "summary": plan.get("summary") or "",
                "quests": [_quest_response(task_by_id.get(item.get("task_id")), item) for item in plan_items if task_by_id.get(item.get("task_id"))],
                "ai_run_id": plan.get("source_ai_run_id"),
                "generated_at": plan.get("generated_at"),
            }

        ranked = _default_rank(tasks)[:5]
        return {
            "quest_plan_id": None,
            "quest_date": quest_date,
            "source": "WORK_ITEM_WORK_DATES",
            "capacity": _capacity_response(capacity),
            "summary": "Working Today tasks are ready for quest generation." if ranked else "Mark tasks as Working Today to generate quests.",
            "quests": [_quest_response(task, _default_quest_item(task, index)) for index, task in enumerate(ranked)],
            "ai_run_id": None,
            "generated_at": None,
        }

    return with_store_lock(action)


def generate_quests(quest_date, request_payload, user_id):
    def action():
        work_items = read_records(WORK_ITEMS_FILE)
        tasks = _candidate_tasks(work_items, user_id, quest_date, request_payload)
        if request_payload.get("from_missions"):
            mission_context = _context(quest_date, tasks, {**request_payload, "max_missions": request_payload.get("max_quests", 5)}, "missions")
            mission_ai = build_mission_ai_output(mission_context)
            mission_ids = [item.get("task_id") for item in mission_ai.get("missions", []) if item.get("is_quest_candidate")]
            if mission_ids:
                tasks = [task for task in tasks if task["task_id"] in set(mission_ids)]

        context = _context(quest_date, tasks, request_payload, "quests")
        ai_runs = read_records(AI_RUNS_FILE)
        quest_plans = read_records(QUEST_PLANS_FILE)
        quest_items = read_records(QUEST_ITEMS_FILE)
        daily_items = read_records(DAILY_WORK_ITEMS_FILE)
        ai_run = _create_ai_run(ai_runs, user_id, "QUEST_PLAN", quest_date, QUEST_SYSTEM_PROMPT, context, request_payload)
        write_records(AI_RUNS_FILE, ai_runs)
        try:
            ai = build_quest_ai_output(context)
            quests = _validated_quests(ai.get("quests") or [], tasks, request_payload.get("max_quests", 5))
            ai = {**ai, "quests": quests}
            plan = _upsert_quest_plan(quest_plans, user_id, quest_date, ai_run["ai_run_id"], ai, context)
            _replace_quest_items(quest_items, plan["quest_plan_id"], quests)
            _upsert_selected_work_dates(work_items, daily_items, user_id, quest_date, quests)
        except Exception as exc:
            _mark_ai_run_failed(ai_runs, ai_run["ai_run_id"], exc)
            write_records(AI_RUNS_FILE, ai_runs)
            raise

        _mark_ai_run_succeeded(ai_runs, ai_run["ai_run_id"], ai)
        write_records(WORK_ITEMS_FILE, work_items)
        write_records(DAILY_WORK_ITEMS_FILE, daily_items)
        write_records(QUEST_PLANS_FILE, quest_plans)
        write_records(QUEST_ITEMS_FILE, quest_items)
        write_records(AI_RUNS_FILE, ai_runs)

        task_by_id = {task["task_id"]: task for task in _user_tasks(work_items, user_id)}
        return {
            "quest_plan_id": plan["quest_plan_id"],
            "quest_date": quest_date,
            "summary": ai.get("summary") or "",
            "quests": [_quest_response(task_by_id.get(item["task_id"]), item) for item in quests if task_by_id.get(item["task_id"])],
            "ai_run_id": ai_run["ai_run_id"],
            "generated_at": ai.get("generated_at"),
        }

    return with_store_lock(action)


def _context(work_date, tasks, request_payload, scope):
    capacity = build_capacity(work_date)
    return {
        "date": work_date,
        "scope": scope,
        "max_items": int(request_payload.get("max_missions") or request_payload.get("max_quests") or 5),
        "capacity": capacity,
        "calendar_events": get_calendar_events(work_date) if request_payload.get("include_calendar", True) else [],
        "candidate_tasks": [_ai_task(task) for task in tasks],
    }


def _candidate_tasks(tasks, user_id, work_date, request_payload):
    candidate_ids = request_payload.get("candidate_task_ids")
    candidate_ids = {int(value) for value in candidate_ids} if candidate_ids else None
    respect_working_today = bool(request_payload.get("respect_working_today", False))
    filtered = []
    for task in _user_tasks(tasks, user_id):
        if task.get("status") in {"Done", "Cancelled"}:
            continue
        if candidate_ids and int(task.get("task_id")) not in candidate_ids:
            continue
        if respect_working_today and work_date not in _worked_dates(task.get("worked_dates")):
            continue
        filtered.append(task)
    return _default_rank(filtered)


def _user_tasks(tasks, user_id):
    return [task for task in tasks if task.get("user_id") == user_id]


def _ai_task(task):
    xp_value = resolve_xp_value(task)
    return {
        "task_id": int(task.get("task_id")),
        "title": task.get("title") or "",
        "description": task.get("description") or "",
        "priority": task.get("priority") or "",
        "status": task.get("status") or "",
        "task_type": task.get("task_type") or "",
        "effort_minutes": int(task.get("estimated_minutes") or task.get("time") or 0),
        "xp_value": xp_value,
        "xp_source": _xp_source(task),
        "rca_tshirt_size": task.get("rca_tshirt_size") or task.get("rcaTshirtSize"),
        "rca_file_change_count": task.get("rca_file_change_count") or task.get("rcaFileChangeCount"),
        "rca_complexity_source": task.get("rca_complexity_source") or task.get("rcaComplexitySource"),
        "impact_score": float(task.get("impact") or task.get("ai_impact_score") or 0),
        "priority_score": float(task.get("priority_score") or task.get("ai_priority_score") or 0),
        "notes": task.get("notes") or "",
        "labels": task.get("labels") or [],
    }


def _default_rank(tasks):
    return sorted(
        tasks,
        key=lambda task: (
            -float(task.get("priority_score") or task.get("ai_priority_score") or 0),
            -float(task.get("impact") or task.get("ai_impact_score") or 0),
            -_priority_weight(task.get("priority")),
            int(task.get("estimated_minutes") or task.get("time") or 0),
            -resolve_xp_value(task),
        ),
    )


def _xp_source(task):
    if task.get("xp_value") not in (None, "") or task.get("xp") not in (None, ""):
        return "explicit"
    if task.get("rca_tshirt_size") or task.get("rcaTshirtSize"):
        return "rca_tshirt_size"
    return "default"


def _validated_missions(missions, tasks, max_items):
    valid_ids = {task["task_id"] for task in tasks}
    seen = set()
    output = []
    for item in sorted(missions, key=lambda value: value.get("rank_order") or 999):
        task_id = item.get("task_id")
        if task_id not in valid_ids or task_id in seen:
            continue
        seen.add(task_id)
        output.append(
            {
                "task_id": task_id,
                "rank_order": len(output) + 1,
                "reason": item.get("reason") or "Recommended by priority, impact, XP, and effort fit.",
                "suggested_action": item.get("suggested_action") or "Start with the smallest verifiable checkpoint.",
                "is_quest_candidate": bool(item.get("is_quest_candidate", True)),
            }
        )
        if len(output) >= max_items:
            break
    return output


def _validated_quests(quests, tasks, max_items):
    valid_ids = {task["task_id"] for task in tasks}
    task_by_id = {task["task_id"]: task for task in tasks}
    seen = set()
    output = []
    for item in sorted(quests, key=lambda value: value.get("rank_order") or 999):
        task_id = item.get("task_id")
        if task_id not in valid_ids or task_id in seen:
            continue
        seen.add(task_id)
        task = task_by_id[task_id]
        output.append(
            {
                "task_id": task_id,
                "rank_order": len(output) + 1,
                "reason": item.get("reason") or "Recommended by priority, impact, XP, and effort fit.",
                "suggested_start_at": item.get("suggested_start_at"),
                "suggested_end_at": item.get("suggested_end_at"),
                "xp_value": int(item.get("xp_value") or resolve_xp_value(task)),
            }
        )
        if len(output) >= max_items:
            break
    return output


def _upsert_quest_plan(plans, user_id, quest_date, ai_run_id, ai, context):
    now = _now_iso()
    plan = _latest_plan(plans, user_id, quest_date)
    if not plan:
        plan = {
            "quest_plan_id": _next_id(plans, "quest_plan_id", 7000),
            "user_id": user_id,
            "quest_date": quest_date,
            "created_at": now,
        }
        plans.append(plan)
    plan.update(
        {
            "summary": ai.get("summary") or "",
            "source_ai_run_id": ai_run_id,
            "capacity": _capacity_response(context["capacity"]),
            "generated_at": ai.get("generated_at") or now,
            "updated_at": now,
        }
    )
    return plan


def _replace_quest_items(items, quest_plan_id, quests):
    items[:] = [item for item in items if item.get("quest_plan_id") != quest_plan_id]
    for quest in quests:
        items.append(
            {
                "quest_item_id": _next_id(items, "quest_item_id", 7100),
                "quest_plan_id": quest_plan_id,
                **quest,
                "created_at": _now_iso(),
            }
        )


def _upsert_selected_work_dates(tasks, daily_items, user_id, quest_date, quests):
    selected_ids = {quest["task_id"] for quest in quests}
    now = _now_iso()
    for task in tasks:
        if task.get("user_id") != user_id or task.get("task_id") not in selected_ids:
            continue
        dates = _worked_dates(task.get("worked_dates"))
        if quest_date not in dates:
            dates.append(quest_date)
        task["worked_dates"] = ",".join(sorted(dates))
        task["working_today"] = task.get("status") != "Done"
        task["workingToday"] = task["working_today"]
        if task["working_today"] and task.get("status") != "Blocked":
            task["status"] = "In Progress"
        task["updated_at"] = now
        task["row_version"] = int(task.get("row_version") or 1) + 1
        _upsert_daily_item(daily_items, task, quest_date, now)


def _upsert_daily_item(daily_items, task, quest_date, now):
    for item in daily_items:
        if item.get("user_id") == task.get("user_id") and item.get("task_id") == task.get("task_id") and item.get("work_date") == quest_date:
            item["is_working_today"] = True
            item["updated_at"] = now
            return
    daily_items.append(
        {
            "daily_work_item_id": _next_id(daily_items, "daily_work_item_id", 6000),
            "user_id": task.get("user_id"),
            "task_id": task.get("task_id"),
            "work_date": quest_date,
            "is_working_today": True,
            "rank_order": None,
            "planned_minutes": task.get("estimated_minutes"),
            "created_at": now,
            "updated_at": now,
        }
    )


def _quest_response(task, quest):
    return {
        "rank_order": quest.get("rank_order"),
        "task_id": task.get("task_id"),
        "title": task.get("title") or "",
        "description": task.get("description") or "",
        "priority": task.get("priority") or "",
        "task_type": task.get("task_type") or "",
        "status": task.get("status") or "",
        "estimated_minutes": int(task.get("estimated_minutes") or task.get("time") or 0),
        "xp_value": int(quest.get("xp_value") or resolve_xp_value(task)),
        "reason": quest.get("reason") or "",
        "suggested_start_at": quest.get("suggested_start_at"),
        "suggested_end_at": quest.get("suggested_end_at"),
        "ai": {
            "difficulty": task.get("difficulty") or task.get("ai_difficulty") or "",
            "impact_score": float(task.get("impact") or task.get("ai_impact_score") or 0),
            "reason": quest.get("reason") or "",
        },
    }


def _default_quest_item(task, index):
    return {
        "rank_order": index + 1,
        "task_id": task["task_id"],
        "reason": "Working Today task ranked by priority, impact, XP, and effort.",
        "suggested_start_at": None,
        "suggested_end_at": None,
        "xp_value": int(task.get("xp_value") or 0),
    }


def _capacity_response(capacity):
    return {
        "workday_minutes": capacity.get("workday_minutes", 0),
        "meeting_minutes": capacity.get("meeting_minutes", 0),
        "available_focus_minutes": capacity.get("available_focus_minutes", 0),
        "suggested_focus_windows": capacity.get("suggested_focus_windows", []),
    }


def _latest_plan(plans, user_id, quest_date):
    matches = [plan for plan in plans if plan.get("user_id") == user_id and plan.get("quest_date") == quest_date]
    return sorted(matches, key=lambda plan: plan.get("updated_at") or plan.get("created_at") or "", reverse=True)[0] if matches else None


def _create_ai_run(ai_runs, user_id, run_type, work_date, system_prompt, context, request_payload):
    now = _now_iso()
    ai_run = {
        "ai_run_id": _next_id(ai_runs, "ai_run_id", 9000),
        "user_id": user_id,
        "run_type": run_type,
        "work_date": work_date,
        "status": "RUNNING",
        "model_id": get_oci_genai_model_id(),
        "request_payload": {
            "system_prompt": system_prompt,
            "request": request_payload,
            "context": context,
        },
        "response_payload": None,
        "error_code": None,
        "error_message": None,
        "created_at": now,
        "updated_at": now,
    }
    ai_runs.append(ai_run)
    return ai_run


def _mark_ai_run_succeeded(ai_runs, ai_run_id, response_payload):
    for run in ai_runs:
        if run.get("ai_run_id") == ai_run_id:
            run["status"] = "SUCCEEDED"
            run["response_payload"] = response_payload
            run["updated_at"] = _now_iso()
            return


def _mark_ai_run_failed(ai_runs, ai_run_id, exc):
    for run in ai_runs:
        if run.get("ai_run_id") == ai_run_id:
            run["status"] = "FAILED"
            run["error_code"] = exc.__class__.__name__
            run["error_message"] = str(exc)
            run["updated_at"] = _now_iso()
            return


def _worked_dates(value):
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return sorted(str(item).strip() for item in value if str(item).strip())
    return sorted(item.strip() for item in str(value).split(",") if item.strip())


def _priority_weight(priority):
    return {"Critical": 10, "High": 8, "Medium": 5, "Low": 3}.get(priority, 0)


def _next_id(records, field, default):
    ids = [record.get(field, 0) for record in records if isinstance(record.get(field), int)]
    return max(ids, default=default) + 1


def _now_iso():
    return datetime.now(timezone.utc).isoformat()
