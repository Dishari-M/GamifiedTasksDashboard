import json
from datetime import datetime, timezone

from fastapi import HTTPException

from config import get_ai_mode, get_ai_provider, get_oci_genai_model_id
from integrations import oci_genai_client
from services.xp_service import XP_MAX, XP_MIN, resolve_xp_value


TASK_ENRICHMENT_SYSTEM_PROMPT = """
You are DevQuest's task enrichment model for a developer productivity dashboard.
Use only the supplied task fields. Do not invent project facts, dates, or external IDs.
Return only valid JSON that matches this schema:
{
  "difficulty": "Easy|Medium|Hard",
  "impact_score": 1-10,
  "priority_score": 0-1,
  "effort_minutes": integer,
  "category": "short category",
  "xp_value": integer,
  "insight": "one concise task-planning insight"
}
""".strip()


def enrich_task_with_ai(task):
    """Return task enrichment from OCI GenAI in real mode, with deterministic fallback in mock mode."""
    mode = get_ai_mode()
    if mode == "mock":
        return _fallback_enrichment(task)
    if mode != "real":
        raise HTTPException(status_code=500, detail=f"Unsupported DEVQUEST_AI_MODE '{mode}'. Use 'mock' or 'real'.")

    provider = get_ai_provider()
    if provider != "oci_genai":
        raise HTTPException(status_code=500, detail=f"Unsupported DEVQUEST_AI_PROVIDER '{provider}'. Use 'oci_genai'.")
    if not get_oci_genai_model_id():
        return _fallback_enrichment(task)

    prompt = (
        "Enrich this task for prioritization and planning. "
        "Respect any user-provided estimate or XP value as evidence, but correct obviously missing values.\n\n"
        f"{json.dumps(_prompt_task(task), indent=2, default=str)}"
    )
    try:
        parsed = oci_genai_client.generate_overview_json(TASK_ENRICHMENT_SYSTEM_PROMPT, prompt)
    except NotImplementedError as exc:
        return _fallback_enrichment(task)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OCI task enrichment failed: {exc}") from exc
    return _normalize_enrichment(parsed, task)


def fallback_task_enrichment(task):
    return _fallback_enrichment(task)


def _prompt_task(task):
    return {
        "title": task.get("title"),
        "description": task.get("description"),
        "task_type": task.get("task_type"),
        "priority": task.get("priority"),
        "status": task.get("status"),
        "estimated_minutes": task.get("estimated_minutes"),
        "actual_minutes": task.get("actual_minutes"),
        "xp_value": task.get("xp_value"),
        "rca_tshirt_size": task.get("rca_tshirt_size"),
        "rca_file_change_count": task.get("rca_file_change_count"),
        "rca_complexity_source": task.get("rca_complexity_source"),
        "notes": task.get("notes"),
        "labels": task.get("labels"),
    }


def _normalize_enrichment(parsed, task):
    fallback = _fallback_enrichment(task)
    if not isinstance(parsed, dict):
        parsed = {}
    effort = _number(parsed.get("effort_minutes"), fallback["effort_minutes"])
    impact = min(10, max(1, _number(parsed.get("impact_score"), fallback["impact_score"])))
    priority_score = min(0.99, max(0.01, _number(parsed.get("priority_score"), fallback["priority_score"])))
    xp_value = min(XP_MAX, max(XP_MIN, int(_number(parsed.get("xp_value"), fallback["xp_value"]))))
    difficulty = str(parsed.get("difficulty") or fallback["difficulty"]).strip().title()
    if difficulty not in {"Easy", "Medium", "Hard"}:
        difficulty = fallback["difficulty"]
    return {
        "difficulty": difficulty,
        "impact_score": impact,
        "priority_score": priority_score,
        "effort_minutes": int(max(15, effort)),
        "category": str(parsed.get("category") or fallback["category"]).strip()[:60],
        "xp_value": xp_value,
        "insight": str(parsed.get("insight") or fallback["insight"]).strip(),
        "model_id": get_oci_genai_model_id(),
        "enriched_at": datetime.now(timezone.utc).isoformat(),
    }


def _fallback_enrichment(task):
    priority_weight = {"Critical": 10, "High": 8, "Medium": 5, "Low": 3}.get(task.get("priority"), 5)
    effort = int(float(task.get("estimated_minutes") or task.get("time") or 60))
    impact = min(10, max(1, priority_weight + (1 if task.get("notes") else 0)))
    priority_score = round(min(0.99, (priority_weight * 0.58 + impact * 0.32 + min(effort / 60, 4) * 0.1) / 10), 2)
    difficulty = "Hard" if effort >= 105 or priority_weight >= 9 else "Easy" if effort <= 35 and priority_weight <= 5 else "Medium"
    xp_value = task.get("xp_value")
    if xp_value in (None, ""):
        xp_value = resolve_xp_value(task)
    return {
        "difficulty": difficulty,
        "impact_score": impact,
        "priority_score": priority_score,
        "effort_minutes": effort,
        "category": task.get("task_type") or "Task",
        "xp_value": int(float(xp_value)),
        "insight": (
            f"{task.get('priority') or 'Medium'} priority {task.get('task_type') or 'Task'} "
            f"with {effort} minutes expected effort."
        ),
        "model_id": get_oci_genai_model_id(),
        "enriched_at": datetime.now(timezone.utc).isoformat(),
    }


def _number(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default or 0)
