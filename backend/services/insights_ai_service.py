import json
from datetime import datetime, timezone

from fastapi import HTTPException

from config import get_ai_mode, get_ai_provider, get_oci_genai_model_id
from integrations import oci_genai_client


TODAY_INSIGHT_SYSTEM_PROMPT = """
You are DevQuest's daily AI insight analyst for a developer.
Use only the supplied task, calendar, capacity, and note evidence.
Do not calculate totals; the backend supplies numeric totals.
When explaining XP, use explicit XP first, then RCA T-shirt complexity if present, then backend fallback values.
Do not invent task names, blockers, meetings, or accomplishments.
Return only valid JSON that matches this schema:
{
  "daily_insight": "1-2 sentence practical insight",
  "risks": ["specific risk, blocker, or empty array"],
  "recommendations": ["specific next action recommendation"],
  "themes": ["short theme labels"]
}
Keep every array to 1-5 concise strings.
""".strip()


def build_today_insight_ai_output(context):
    mode = get_ai_mode()
    if mode == "mock":
        return _mock_output(context)
    if mode != "real":
        raise HTTPException(
            status_code=500,
            detail=f"Unsupported DEVQUEST_AI_MODE '{mode}'. Use 'mock' or 'real'.",
        )

    provider = get_ai_provider()
    if provider != "oci_genai":
        raise HTTPException(
            status_code=500,
            detail=f"Unsupported DEVQUEST_AI_PROVIDER '{provider}'. Use 'oci_genai'.",
        )
    if not get_oci_genai_model_id():
        raise HTTPException(
            status_code=501,
            detail="DEVQUEST_AI_MODE=real requires OCI_GENAI_MODEL_ID before OCI Generative AI can be called.",
        )

    user_prompt = (
        "Generate today's insight from this JSON context. Preserve exact task titles. "
        "If evidence is thin, say what is known instead of guessing.\n\n"
        f"{json.dumps(context, indent=2, default=str)}"
    )
    try:
        parsed = oci_genai_client.generate_overview_json(TODAY_INSIGHT_SYSTEM_PROMPT, user_prompt)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OCI insight generation failed: {exc}") from exc

    return _normalize_output(parsed, context)


def _mock_output(context):
    tasks = context.get("tasks", [])
    completed = context.get("completed_tasks", [])
    capacity = context.get("capacity", {})
    top_task = tasks[0] if tasks else None
    available = capacity.get("available_focus_minutes", 0)
    risks = []
    recommendations = []

    if top_task:
        effort = top_task.get("effort_minutes") or 0
        if effort > available:
            risks.append(f"{top_task['title']} may exceed today's available focus time.")
        recommendations.append(f"Start with {top_task['title']} and split it into a focused first checkpoint.")
    else:
        recommendations.append("Mark at least one task as Working Today before generating focused recommendations.")

    if capacity.get("meeting_minutes", 0) > available:
        risks.append("Meeting load is higher than available focus time.")

    insight = f"You have {available} focus minutes available."
    if top_task:
        insight = f"You have {available} focus minutes available. The highest leverage task is {top_task['title']}."
    if completed:
        insight = f"{insight} {len(completed)} task(s) are already completed for this date."

    return {
        "daily_insight": insight,
        "risks": risks,
        "recommendations": recommendations,
        "themes": _themes(context),
        "generated_at": _generated_at(),
    }


def _normalize_output(parsed, context):
    if not isinstance(parsed, dict):
        parsed = {}
    fallback = _mock_output(context)
    return {
        "daily_insight": str(parsed.get("daily_insight") or parsed.get("summary") or fallback["daily_insight"]),
        "risks": _list(parsed.get("risks")) if parsed.get("risks") is not None else fallback["risks"],
        "recommendations": _list(parsed.get("recommendations")) or fallback["recommendations"],
        "themes": _list(parsed.get("themes")) or fallback["themes"],
        "generated_at": _generated_at(),
    }


def _list(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()][:5]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _themes(context):
    values = []
    for task in context.get("tasks", []) + context.get("completed_tasks", []):
        values.extend(task.get("labels") or [])
        if task.get("task_type"):
            values.append(task["task_type"])
        if task.get("priority"):
            values.append(task["priority"])
    seen = []
    for value in values:
        label = str(value).strip()
        if label and label not in seen:
            seen.append(label)
    return seen[:5]


def _generated_at():
    return datetime.now(timezone.utc).isoformat()
