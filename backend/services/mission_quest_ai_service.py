import json
from datetime import datetime

from fastapi import HTTPException

from config import get_ai_mode, get_ai_provider, get_oci_genai_model_id
from integrations import oci_genai_client


MISSION_SYSTEM_PROMPT = """
You are DevQuest's mission planner for a developer.
Use only the supplied task and capacity evidence.
Recommend missions based on priority, XP, time available, time needed, impact, and notes.
Do not invent tasks or task IDs.
Return only valid JSON that matches this schema:
{
  "summary": "1-2 sentence summary",
  "missions": [
    {
      "task_id": 1001,
      "rank_order": 1,
      "reason": "specific evidence-based reason",
      "suggested_action": "specific next action",
      "is_quest_candidate": true
    }
  ]
}
""".strip()


QUEST_SYSTEM_PROMPT = """
You are DevQuest's daily quest route planner for a developer.
Use only the supplied task, calendar, and capacity evidence.
Rank a practical quest plan that fits available focus time when possible.
Do not invent tasks or task IDs.
Return only valid JSON that matches this schema:
{
  "summary": "1-2 sentence quest plan summary",
  "quests": [
    {
      "task_id": 1001,
      "rank_order": 1,
      "reason": "specific evidence-based reason",
      "suggested_start_at": "ISO timestamp or null",
      "suggested_end_at": "ISO timestamp or null",
      "xp_value": 120
    }
  ]
}
""".strip()


def build_mission_ai_output(context):
    return _build_ai_output("missions", MISSION_SYSTEM_PROMPT, context)


def build_quest_ai_output(context):
    return _build_ai_output("quests", QUEST_SYSTEM_PROMPT, context)


def _build_ai_output(kind, system_prompt, context):
    mode = get_ai_mode()
    if mode == "mock":
        return _mock_output(kind, context)
    if mode != "real":
        raise HTTPException(status_code=500, detail=f"Unsupported DEVQUEST_AI_MODE '{mode}'. Use 'mock' or 'real'.")

    provider = get_ai_provider()
    if provider != "oci_genai":
        raise HTTPException(status_code=500, detail=f"Unsupported DEVQUEST_AI_PROVIDER '{provider}'. Use 'oci_genai'.")
    if not get_oci_genai_model_id():
        raise HTTPException(
            status_code=501,
            detail="DEVQUEST_AI_MODE=real requires OCI_GENAI_MODEL_ID before OCI Generative AI can be called.",
        )

    user_prompt = (
        f"Generate {kind} from this JSON context.\n"
        "Keep IDs exactly as supplied. Prefer fewer recommendations over weak recommendations.\n\n"
        f"{json.dumps(context, indent=2, default=str)}"
    )
    try:
        parsed = oci_genai_client.generate_overview_json(system_prompt, user_prompt)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OCI {kind} generation failed: {exc}") from exc
    return _normalize_output(kind, parsed, context)


def _mock_output(kind, context):
    tasks = _ranked_tasks(context)
    if kind == "missions":
        missions = [
            {
                "task_id": task["task_id"],
                "rank_order": index + 1,
                "reason": _reason(task, context),
                "suggested_action": _action(task),
                "is_quest_candidate": index < context.get("max_items", 5),
            }
            for index, task in enumerate(tasks[: context.get("max_items", 5)])
        ]
        return {
            "summary": _summary(missions, tasks),
            "missions": missions,
            "generated_at": _generated_at(),
        }

    windows = context.get("capacity", {}).get("suggested_focus_windows", [])
    quests = []
    cursor = 0
    for index, task in enumerate(tasks[: context.get("max_items", 5)]):
        start_at, end_at = _suggested_window(windows, cursor, task.get("effort_minutes") or 0)
        cursor += 1
        quests.append(
            {
                "task_id": task["task_id"],
                "rank_order": index + 1,
                "reason": _reason(task, context),
                "suggested_start_at": start_at,
                "suggested_end_at": end_at,
                "xp_value": task.get("xp_value") or 0,
            }
        )
    return {
        "summary": _summary(quests, tasks),
        "quests": quests,
        "generated_at": _generated_at(),
    }


def _normalize_output(kind, parsed, context):
    if not isinstance(parsed, dict):
        parsed = {}
    fallback = _mock_output(kind, context)
    key = "missions" if kind == "missions" else "quests"
    items = parsed.get(key)
    if not isinstance(items, list):
        items = []
    normalized = {
        "summary": str(parsed.get("summary") or fallback["summary"]),
        key: [_normalize_item(kind, item) for item in items if isinstance(item, dict)],
        "generated_at": _generated_at(),
    }
    if not normalized[key]:
        normalized[key] = fallback[key]
    return normalized


def _normalize_item(kind, item):
    base = {
        "task_id": _int(item.get("task_id")),
        "rank_order": _int(item.get("rank_order")),
        "reason": str(item.get("reason") or "").strip(),
    }
    if kind == "missions":
        base["suggested_action"] = str(item.get("suggested_action") or "").strip()
        base["is_quest_candidate"] = bool(item.get("is_quest_candidate", True))
        return base
    base["suggested_start_at"] = item.get("suggested_start_at") or None
    base["suggested_end_at"] = item.get("suggested_end_at") or None
    base["xp_value"] = _int(item.get("xp_value"))
    return base


def _ranked_tasks(context):
    return sorted(
        context.get("candidate_tasks", []),
        key=lambda task: (
            -float(task.get("priority_score") or 0),
            -float(task.get("impact_score") or 0),
            -_priority_weight(task.get("priority")),
            int(task.get("effort_minutes") or 0),
            -int(task.get("xp_value") or 0),
        ),
    )


def _reason(task, context):
    available = context.get("capacity", {}).get("available_focus_minutes", 0)
    if task.get("effort_minutes") and task["effort_minutes"] <= available:
        return "High-value work that fits the available focus window."
    if task.get("priority") in {"Critical", "High"}:
        return "High-priority work with strong impact signals."
    return "Good follow-up based on priority, impact, XP, and effort."


def _action(task):
    if task.get("task_type") == "Bug":
        return "Reproduce, fix, and add regression coverage."
    if task.get("task_type") == "Review":
        return "Review the change and leave concise feedback."
    if task.get("task_type") == "Meeting":
        return "Prepare notes and capture action items."
    return "Start with the smallest verifiable checkpoint."


def _summary(items, tasks):
    if not items:
        return "No eligible task evidence is available for recommendations."
    first = next((task for task in tasks if task["task_id"] == items[0]["task_id"]), None)
    if first:
        return f"Start with {first['title']} because it has the strongest priority, impact, and fit signals."
    return "Use the ranked recommendations as the next focused work path."


def _suggested_window(windows, index, effort_minutes):
    if not windows:
        return None, None
    window = windows[min(index, len(windows) - 1)]
    start_at = window.get("start_at")
    end_at = window.get("end_at")
    if not start_at or not effort_minutes:
        return start_at, end_at
    try:
        start_dt = datetime.fromisoformat(start_at)
        end_dt = start_dt + (datetime.fromisoformat(end_at) - datetime.fromisoformat(start_at))
        if effort_minutes < window.get("duration_minutes", effort_minutes):
            from datetime import timedelta

            end_dt = start_dt + timedelta(minutes=effort_minutes)
        return start_dt.isoformat(), end_dt.isoformat()
    except (TypeError, ValueError):
        return start_at, end_at


def _priority_weight(priority):
    return {"Critical": 10, "High": 8, "Medium": 5, "Low": 3}.get(priority, 0)


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _generated_at():
    return datetime.now().astimezone().isoformat(timespec="seconds")
