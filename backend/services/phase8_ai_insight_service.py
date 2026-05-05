from datetime import datetime

from fastapi import HTTPException

from config import get_ai_mode, get_ai_provider, get_oci_genai_model_id
from integrations import oci_genai_client


def _generated_at():
    """Return the current local timestamp for generated insight metadata."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _mock_insight(capacity, top_missions, planned_tasks):
    """Build a deterministic dashboard insight without calling an AI provider."""
    impact_score = max((task["ai_impact_score"] for task in planned_tasks), default=0)
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
        raise HTTPException(
            status_code=501,
            detail="DEVQUEST_AI_MODE=real requires OCI_GENAI_MODEL_ID before OCI Generative AI can be called.",
        )

    try:
        insight = oci_genai_client.generate_dashboard_insight(
            _prompt_payload(work_date, capacity, top_missions, tasks, schedule)
        )
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"OCI Generative AI call failed: {exc}",
        ) from exc

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
