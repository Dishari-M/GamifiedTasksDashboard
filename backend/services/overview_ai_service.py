import json
from datetime import datetime

from fastapi import HTTPException

from config import get_ai_mode, get_ai_provider, get_oci_genai_model_id
from integrations import oci_genai_client


DAILY_OVERVIEW_SYSTEM_PROMPT = """
You are Gamified Tasks Dashboard's productivity insight analyst for a developer.
Use only the supplied task, work-date, focus-session, calendar, and existing daily overview evidence.
Treat existing daily_overviews as saved user reflection and prior overview context for continuity.
Do not calculate totals; the backend supplies numeric totals.
Do not invent task names, meetings, blockers, or accomplishments.
Return only valid JSON that matches this schema:
{
  "summary": "1-2 sentence evidence-based day summary",
  "new_learnings": ["specific learning inferred from notes or work"],
  "went_well": ["specific positive outcome"],
  "went_wrong": ["specific friction, risk, blocker, or empty array"],
  "themes": ["short theme labels"]
}
Keep every array to 1-5 concise strings.
""".strip()


WEEKLY_OVERVIEW_SYSTEM_PROMPT = """
You are Gamified Tasks Dashboard's weekly productivity analyst for a developer.
Use only the supplied daily_overviews, completed tasks, work-date rows, focus sessions, and calendar evidence.
Do not calculate totals; the backend supplies numeric totals.
Separate evidence from interpretation, and avoid motivational filler.
Return only valid JSON that matches this schema:
{
  "summary": "2-3 sentence weekly insight",
  "top_accomplishments": ["specific completed outcome"],
  "new_learnings": ["learning or pattern from notes"],
  "themes": ["short theme labels"],
  "went_well": ["specific positive pattern"],
  "went_wrong": ["specific friction, risk, blocker, or empty array"]
}
Keep every array to 1-6 concise strings.
""".strip()


def _generated_at():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _user_prompt(scope, context):
    return (
        f"Generate the {scope} overview from this JSON context.\n"
        "Preserve exact task titles when mentioning tasks. "
        "If evidence is thin, say what is known instead of guessing.\n\n"
        f"{json.dumps(context, indent=2, default=str)}"
    )


def build_daily_ai_output(context):
    return _build_ai_output(
        scope="daily",
        system_prompt=DAILY_OVERVIEW_SYSTEM_PROMPT,
        user_prompt=_user_prompt("daily", context),
        context=context,
    )


def build_weekly_ai_output(context):
    return _build_ai_output(
        scope="weekly",
        system_prompt=WEEKLY_OVERVIEW_SYSTEM_PROMPT,
        user_prompt=_user_prompt("weekly", context),
        context=context,
    )


def build_daily_fallback_output(context):
    return _mock_output("daily", context)


def build_weekly_fallback_output(context):
    return _mock_output("weekly", context)


def _build_ai_output(scope, system_prompt, user_prompt, context):
    mode = get_ai_mode()
    if mode == "mock":
        return _mock_output(scope, context)
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

    try:
        parsed = oci_genai_client.generate_overview_json(system_prompt, user_prompt)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OCI overview generation failed: {exc}") from exc

    return _normalize_output(scope, parsed, context)


def _mock_output(scope, context):
    completed = context.get("completed_tasks", [])
    focus = context.get("focus_sessions", [])
    daily_overviews = context.get("daily_overviews", [])
    saved_learnings = _daily_overview_items(daily_overviews, "new_learnings")
    saved_went_well = _daily_overview_items(daily_overviews, "went_well")
    saved_went_wrong = _daily_overview_items(daily_overviews, "went_wrong")
    saved_summaries = [
        str(item.get("summary")).strip()
        for item in daily_overviews
        if item.get("summary") and str(item.get("summary")).strip()
    ]
    notes = [
        value
        for item in completed + focus
        for value in [item.get("notes") or item.get("outcome_note")]
        if value
    ] + saved_learnings + saved_went_well + saved_went_wrong + saved_summaries
    themes = _themes(context)
    first_title = completed[0]["title"] if completed else None

    if scope == "weekly":
        top_accomplishments = [task["title"] for task in completed[:5]]
        if not top_accomplishments:
            top_accomplishments = saved_went_well[:5]
        summary = (
            f"The week closed {len(completed)} task(s) with {context['metrics']['focus_minutes']} minutes of focus time. "
            f"The strongest signals are {', '.join(themes[:3]) if themes else 'task completion and focus follow-through'}."
        )
        if saved_summaries:
            summary = f"{summary} Saved daily overview context covers {len(saved_summaries)} day(s)."
        return {
            "summary": summary,
            "top_accomplishments": top_accomplishments or ["No completed task evidence is available yet."],
            "new_learnings": saved_learnings[:6] or _learning_items(notes),
            "themes": themes,
            "went_well": saved_went_well[:6] or _went_well(completed, focus),
            "went_wrong": saved_went_wrong[:6] or _went_wrong(notes, context),
            "generated_at": _generated_at(),
        }

    summary = (
        f"Completed {len(completed)} task(s), protected {context['metrics']['focus_minutes']} focus minutes, "
        f"and spent {context['metrics']['meeting_minutes']} minutes in meetings."
    )
    if first_title:
        summary = f"{summary} The clearest accomplishment was {first_title}."
    if saved_summaries:
        summary = f"{summary} Saved reflection noted: {saved_summaries[0][:180]}"
    return {
        "summary": summary,
        "new_learnings": saved_learnings[:5] or _learning_items(notes),
        "went_well": saved_went_well[:5] or _went_well(completed, focus),
        "went_wrong": saved_went_wrong[:5] or _went_wrong(notes, context),
        "themes": themes,
        "generated_at": _generated_at(),
    }


def _normalize_output(scope, parsed, context):
    if not isinstance(parsed, dict):
        parsed = {}
    saved_learnings = _daily_overview_items(context.get("daily_overviews", []), "new_learnings")
    saved_went_well = _daily_overview_items(context.get("daily_overviews", []), "went_well")
    saved_went_wrong = _daily_overview_items(context.get("daily_overviews", []), "went_wrong")
    normalized = {
        "summary": str(parsed.get("summary") or _mock_output(scope, context)["summary"]),
        "new_learnings": _list(parsed.get("new_learnings")) or saved_learnings or _learning_items([]),
        "went_well": _list(parsed.get("went_well")) or saved_went_well or _went_well(context.get("completed_tasks", []), context.get("focus_sessions", [])),
        "went_wrong": _list(parsed.get("went_wrong")) or saved_went_wrong,
        "themes": _list(parsed.get("themes")) or _themes(context),
        "generated_at": _generated_at(),
    }
    if scope == "weekly":
        normalized["top_accomplishments"] = _list(parsed.get("top_accomplishments")) or [
            task["title"] for task in context.get("completed_tasks", [])[:5]
        ] or saved_went_well[:6]
    _merge_saved_daily_overview_reflections(normalized, context, 6 if scope == "weekly" else 5)
    return normalized


def _list(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()][:6]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _daily_overview_items(daily_overviews, field):
    items = []
    for overview in daily_overviews:
        for value in _list(overview.get(field)):
            if value not in items:
                items.append(value)
    return items


def _merge_saved_daily_overview_reflections(output, context, limit):
    for field in ("new_learnings", "went_well", "went_wrong"):
        saved = _daily_overview_items(context.get("daily_overviews", []), field)
        if saved:
            output[field] = _merge_text_items(saved, output.get(field, []), limit)
    return output


def _merge_text_items(primary, secondary, limit):
    merged = []
    for value in list(primary or []) + list(secondary or []):
        text = str(value).strip()
        if text and text not in merged:
            merged.append(text)
    return merged[:limit]


def _themes(context):
    values = []
    for task in context.get("completed_tasks", []) + context.get("worked_tasks", []):
        values.extend(task.get("labels") or [])
        if task.get("task_type"):
            values.append(task["task_type"])
        if task.get("ai_category"):
            values.append(task["ai_category"])
    seen = []
    for value in values:
        label = str(value).strip()
        if label and label not in seen:
            seen.append(label)
    return seen[:5]


def _learning_items(notes):
    if notes:
        return [str(notes[0]).strip()[:180]]
    return ["No explicit learning notes were captured yet."]


def _went_well(completed, focus):
    if completed:
        return [f"Completed {len(completed)} task(s) with durable work evidence."]
    if focus:
        return [f"Captured {len(focus)} focus session(s) for deep-work evidence."]
    return ["No completed work evidence is available yet."]


def _went_wrong(notes, context):
    text = " ".join(notes).lower()
    signals = ["blocked", "risk", "issue", "timeout", "failed", "wrong", "delay"]
    if any(signal in text for signal in signals):
        return ["Notes include friction or risk signals that should be reviewed."]
    if context.get("metrics", {}).get("meeting_minutes", 0) > context.get("metrics", {}).get("focus_minutes", 0):
        return ["Meeting load outweighed captured focus time."]
    return []
