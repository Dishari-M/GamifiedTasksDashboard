from datetime import datetime
import logging

from fastapi import HTTPException

from config import get_ai_mode, get_ai_provider, get_oci_genai_model_id
from integrations import oci_genai_client


logger = logging.getLogger(__name__)


def _generated_at():
    """Return the current local timestamp for generated insight metadata."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _task_impact_score(task):
    if "ai_impact_score" in task and task["ai_impact_score"] is not None:
        return task["ai_impact_score"]
    ai = task.get("ai") or {}
    return ai.get("impact_score", 0)


def _mock_insight(capacity, top_missions, planned_tasks):
    """Build a deterministic dashboard insight without calling an AI provider."""
    impact_score = max((_task_impact_score(task) for task in planned_tasks), default=0)
    first_mission = top_missions[0]["title"] if top_missions else "the highest priority mission"
    return {
        "text": f"You have {capacity['available_focus_minutes']} focus minutes after meetings. Start with {first_mission}.",
        "capacity_minutes": capacity["available_focus_minutes"],
        "impact_score": impact_score,
        "generated_at": _generated_at(),
    }


def _prompt_payload(work_date, capacity, top_missions, tasks, schedule):
    """Build the compact payload that will be sent to OCI GenAI in real mode."""
    return {
        "date": work_date,
        "capacity": capacity,
        "top_missions": top_missions,
        "tasks": tasks,
        "schedule": schedule,
        "instruction": (
            "Generate one concise dashboard insight for a developer. "
            "Use the available focus minutes, meetings, and top missions. "
            "Return JSON with text, capacity_minutes, and impact_score."
        ),
    }


def _real_insight(work_date, capacity, top_missions, tasks, schedule):
    """Call the configured real AI provider for dashboard insight generation."""
    provider = get_ai_provider()
    if provider != "oci_genai":
        raise HTTPException(
            status_code=500,
            detail=f"Unsupported DEVQUEST_AI_PROVIDER '{provider}'. Use 'oci_genai'.",
        )

    model_id = get_oci_genai_model_id()
    if not model_id:
        logger.warning("Dashboard insight falling back to deterministic output because OCI_GENAI_MODEL_ID is not configured.")
        return _mock_insight(capacity, top_missions, tasks)

    try:
        insight = oci_genai_client.generate_dashboard_insight(
            _prompt_payload(work_date, capacity, top_missions, tasks, schedule)
        )
    except NotImplementedError as exc:
        logger.warning("Dashboard insight OCI client is not implemented locally; using deterministic fallback.")
        return _mock_insight(capacity, top_missions, tasks)
    except Exception as exc:
        logger.exception("Dashboard insight OCI call failed; using deterministic fallback.")
        return _mock_insight(capacity, top_missions, tasks)

    return {
        **insight,
        "generated_at": insight.get("generated_at") or _generated_at(),
    }


def build_ai_insight(work_date, capacity, top_missions, tasks, schedule, planned_tasks):
    """Return dashboard AI insight using mock or real mode based on shared config."""
    mode = get_ai_mode()
    if mode == "mock":
        return _mock_insight(capacity, top_missions, planned_tasks)
    if mode == "real":
        return _real_insight(work_date, capacity, top_missions, tasks, schedule)
    raise HTTPException(
        status_code=500,
        detail=f"Unsupported DEVQUEST_AI_MODE '{mode}'. Use 'mock' or 'real'.",
    )
