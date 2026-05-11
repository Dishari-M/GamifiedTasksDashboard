import json
import re
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException

from config import get_ai_mode, get_ai_provider, get_oci_genai_model_id, get_data_mode
from integrations import oci_genai_client
from db import get_connection
from repositories import overview_repository, standup_repository
from services.api_cache import canonical_cache_key, get_cached_response, get_default_cache_ttl_seconds, invalidate_user_cache, set_cached_response
from services.filesystem_store import read_records, with_store_lock
from services.oracle_user_service import parse_oracle_user_id


WORK_ITEMS_FILE = "work_items.json"
STANDUP_CACHE_NAMESPACE = "standup_note"


STANDUP_SYSTEM_PROMPT = """
You are Gamified Tasks Dashboard's scrum-call standup note writer for a developer.
Use only the supplied current-date evidence: work items, task notes, focus sessions, daily overviews, meetings, and blockers.
Write exactly five concise first-person sentences suitable to read aloud in a scrum call.
Mention accomplishments, current focus, next steps, and blockers or risks if present.
Do not invent task names, meetings, blockers, or completed work.
Return only valid JSON that matches this schema:
{
  "sentences": ["sentence 1", "sentence 2", "sentence 3", "sentence 4", "sentence 5"],
  "accomplished": "brief completed-work summary",
  "in_progress": "brief active-work summary",
  "blockers": "brief blockers or risks summary"
}
""".strip()


def standup_note_response(date=None, user_id="local-user"):
    work_date = _resolve_work_date(date)
    cache_user_id = parse_oracle_user_id(user_id) if get_data_mode() == "oracle" else user_id
    cache_key = canonical_cache_key({"mode": get_data_mode(), "user_id": cache_user_id, "date": work_date})
    cached = get_cached_response(STANDUP_CACHE_NAMESPACE, cache_key, get_default_cache_ttl_seconds())
    if cached is not None:
        return {"data": cached, "meta": {"request_id": str(uuid4()), "cache": "hit"}}
    data = build_standup_note(work_date, user_id)
    set_cached_response(STANDUP_CACHE_NAMESPACE, cache_key, data, user_id=cache_user_id)
    return {"data": data, "meta": {"request_id": str(uuid4()), "cache": "miss"}}


def generate_standup_note_response(payload, user_id="local-user"):
    work_date = _resolve_work_date(payload.date)
    if get_data_mode() == "oracle":
        invalidate_user_cache(parse_oracle_user_id(user_id), (STANDUP_CACHE_NAMESPACE,))
    return {
        "data": build_standup_note(work_date, user_id, force=payload.force),
        "meta": {"request_id": str(uuid4())},
    }


def build_standup_note(work_date, user_id="local-user", force=False):
    if get_data_mode() == "oracle":
        return _oracle_standup_note(work_date, user_id, force=force)

    context = _standup_context(work_date, user_id)
    if not force or get_ai_mode() == "mock":
        note = _mock_note(context)
    elif get_ai_mode() == "real":
        note = _real_note(context)
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Unsupported DEVQUEST_AI_MODE '{get_ai_mode()}'. Use 'mock' or 'real'.",
        )

    return _response(context, note, force)


def _oracle_standup_note(work_date, user_id, force=False):
    conn = None
    ai_run_id = None
    oracle_user_id = parse_oracle_user_id(user_id)
    try:
        conn = get_connection()
        cur = conn.cursor()
        context = standup_repository.build_context(cur, oracle_user_id, work_date)
        if not force:
            note = _mock_note(context)
            return _response(context, note, force, standup_note_id=None, ai_run_id=None)

        ai_run_id = overview_repository.insert_ai_run(
            cur,
            oracle_user_id,
            "STANDUP_NOTE",
            get_oci_genai_model_id(),
            {
                "run_type": "STANDUP_NOTE",
                "model_id": get_oci_genai_model_id(),
                "system_prompt": STANDUP_SYSTEM_PROMPT,
                "context": context,
                "force": bool(force),
            },
        )
        conn.commit()
    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except Exception as exc:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=503, detail="Standup note storage is unavailable.") from exc
    finally:
        if conn:
            conn.close()

    try:
        note = _real_note(context) if get_ai_mode() == "real" else _mock_note(context)
        note["full_note"] = " ".join(_exactly_five(note["sentences"]))
        _update_ai_run_success(ai_run_id, note)
    except Exception as exc:
        note = _mock_note(context)
        note["full_note"] = " ".join(_exactly_five(note["sentences"]))
        _mark_ai_run_failed(ai_run_id, f"Standup generation failed: {_exception_message(exc)}")

    return _response(
        context,
        note,
        force,
        standup_note_id=None,
        ai_run_id=ai_run_id,
    )


def _standup_context(work_date, user_id):
    def action():
        tasks = [
            _normalize_task(task)
            for task in read_records(WORK_ITEMS_FILE)
            if task.get("user_id") == user_id
        ]
        today_tasks = [task for task in tasks if _is_working_on_date(task, work_date)]
        completed = [task for task in tasks if _date_part(task.get("completed_at")) == work_date]
        blockers = [
            task
            for task in tasks
            if task.get("status") == "Blocked" and (_is_working_on_date(task, work_date) or not today_tasks)
        ]
        return {
            "date": work_date,
            "metrics": {
                "today_task_count": len(today_tasks),
                "completed_count": len(completed),
                "blocker_count": len(blockers),
                "planned_minutes": sum(task["estimated_minutes"] for task in today_tasks),
                "focus_session_count": 0,
                "focus_minutes": 0,
                "meeting_count": 0,
                "meeting_minutes": 0,
                "daily_overview_count": 0,
                "note_count": len(_notes_from_tasks(today_tasks + completed + blockers)),
            },
            "today_work_items": _sort_tasks(today_tasks),
            "completed_today": _sort_tasks(completed),
            "blockers": _sort_tasks(blockers),
            "today_notes": _notes_from_tasks(today_tasks + completed + blockers),
            "focus_sessions": [],
            "calendar_events": [],
            "meetings": [],
            "daily_overviews": [],
        }

    return with_store_lock(action)


def _real_note(context):
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

    prompt = (
        "Generate a five-sentence scrum standup note from this JSON context.\n"
        "Preserve exact task titles when mentioning tasks. "
        "If there are no blockers, state that directly in one sentence.\n\n"
        f"{json.dumps(context, indent=2, default=str)}"
    )
    try:
        parsed = oci_genai_client.generate_overview_json(STANDUP_SYSTEM_PROMPT, prompt)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OCI standup generation failed: {exc}") from exc
    return _normalize_note(parsed, context)


def _mock_note(context):
    completed = context["completed_today"]
    in_progress = [task for task in context["today_work_items"] if task["status"] not in {"Done", "Blocked"}]
    blockers = context["blockers"]

    completed_text = _task_titles(completed) or "No completed tasks are logged yet"
    progress_text = _task_titles(in_progress) or "No active in-progress tasks are selected"
    blocker_text = _blocker_text(blockers)
    reflection_text = _daily_overview_text(context.get("daily_overviews", [])) or _notes_text(context.get("today_notes", []))
    meeting_text = _meeting_text(context)
    focus_text = _focus_text(context)
    next_task = in_progress[0]["title"] if in_progress else (context["today_work_items"][0]["title"] if context["today_work_items"] else "the next highest-priority item")
    planned_minutes = context["metrics"]["planned_minutes"]

    return {
        "sentences": [
            f"Today I completed {completed_text}.",
            f"Today I am focused on {progress_text}.",
            f"My next step is to move {next_task} forward using {reflection_text}.",
            f"I have {planned_minutes} planned minutes, {focus_text}, and {meeting_text}.",
            f"Blockers or risks: {blocker_text}.",
        ],
        "accomplished": completed_text,
        "in_progress": progress_text,
        "blockers": blocker_text,
    }


def _normalize_note(parsed, context):
    if not isinstance(parsed, dict):
        parsed = {}
    fallback = _mock_note(context)
    sentences = _sentences(parsed.get("sentences"))
    if len(sentences) < 5:
        sentences = _sentences(parsed.get("standup_note") or parsed.get("full_note") or parsed.get("summary"))
    if len(sentences) < 5:
        sentences = fallback["sentences"]
    sentences = _exactly_five(sentences)
    return {
        "sentences": sentences,
        "accomplished": str(parsed.get("accomplished") or fallback["accomplished"]),
        "in_progress": str(parsed.get("in_progress") or parsed.get("inProgress") or fallback["in_progress"]),
        "blockers": str(parsed.get("blockers") or fallback["blockers"]),
    }


def _response(context, note, force, standup_note_id=None, ai_run_id=None, generated_at=None):
    full_note = " ".join(_exactly_five(note["sentences"]))
    generated_at = generated_at or datetime.now().astimezone().isoformat(timespec="seconds")
    return {
        "date": context["date"],
        "standup_note_id": standup_note_id,
        "ai_run_id": ai_run_id,
        "mode": get_ai_mode(),
        "model_id": get_oci_genai_model_id(),
        "force": bool(force),
        "sentences": _exactly_five(note["sentences"]),
        "full_note": full_note,
        "fullNote": full_note,
        "accomplished": note["accomplished"],
        "in_progress": note["in_progress"],
        "inProgress": note["in_progress"],
        "blockers": note["blockers"],
        "context": context,
        "generated_at": generated_at,
        "generatedAt": generated_at,
    }


def _update_ai_run_success(ai_run_id, response_payload):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        overview_repository.update_ai_run(cur, ai_run_id, "SUCCEEDED", response_payload)
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


def _mark_ai_run_failed(ai_run_id, message):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        overview_repository.update_ai_run(cur, ai_run_id, "FAILED", None, "AI_PROVIDER_ERROR", message)
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


def _exception_message(exc):
    if isinstance(exc, HTTPException):
        return str(exc.detail)
    return str(exc)


def _normalize_task(task):
    return {
        "task_id": task.get("task_id") or task.get("id"),
        "external_id": task.get("external_id") or task.get("externalId") or "",
        "title": task.get("title") or "",
        "description": task.get("description") or "",
        "source": task.get("external_source") or task.get("source") or "Custom",
        "task_type": task.get("task_type") or task.get("type") or "Task",
        "priority": task.get("priority") or "Medium",
        "status": task.get("status") or "To Do",
        "estimated_minutes": int(float(task.get("estimated_minutes") or task.get("time") or 0)),
        "actual_minutes": int(float(task.get("actual_minutes") or task.get("actualMinutes") or 0)),
        "xp_value": int(float(task.get("xp_value") or task.get("xp") or 0)),
        "notes": task.get("notes") or "",
        "labels": task.get("labels") if isinstance(task.get("labels"), list) else [],
        "worked_dates": _worked_dates(task),
        "working_today": bool(task.get("working_today") or task.get("workingToday")),
        "completed_at": task.get("completed_at") or task.get("completedAt"),
        "ai_insight": task.get("ai_insight") or task.get("aiInsight") or "",
        "priority_score": float(task.get("priority_score") or task.get("priorityScore") or 0),
    }


def _notes_from_tasks(tasks):
    notes = []
    for task in tasks:
        note = str(task.get("notes") or "").strip()
        if note and note not in notes:
            notes.append(note)
    return notes


def _sort_tasks(tasks):
    return sorted(
        tasks,
        key=lambda task: (
            task["status"] == "Done",
            -task["priority_score"],
            -task["xp_value"],
            task["title"],
        ),
    )


def _resolve_work_date(value=None):
    if value:
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Date must use YYYY-MM-DD format.") from exc
        return value
    return datetime.now().astimezone().date().isoformat()


def _worked_dates(task):
    raw = task.get("worked_dates")
    if raw is None:
        raw = task.get("workedDates")
    if isinstance(raw, list):
        return [str(item) for item in raw if str(item).strip()]
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def _is_working_on_date(task, work_date):
    return task.get("status") != "Done" and (work_date in task.get("worked_dates", []) or bool(task.get("working_today")))


def _date_part(value):
    return str(value or "")[:10]


def _task_titles(tasks):
    return "; ".join(task["title"] for task in tasks if task.get("title"))


def _daily_overview_text(daily_overviews):
    if not daily_overviews:
        return ""
    overview = daily_overviews[0]
    parts = []
    if overview.get("summary"):
        parts.append(overview["summary"])
    for field in ("new_learnings", "went_well", "went_wrong"):
        values = overview.get(field) or []
        if values:
            parts.append("; ".join(str(value) for value in values[:2]))
    return "; ".join(parts)[:220]


def _notes_text(notes):
    if not notes:
        return "the latest notes and acceptance criteria"
    return "; ".join(str(note) for note in notes[:2])[:220]


def _meeting_text(context):
    count = context.get("metrics", {}).get("meeting_count", 0)
    minutes = context.get("metrics", {}).get("meeting_minutes", 0)
    if not count:
        return "no meetings captured"
    return f"{count} meeting(s) totaling {minutes} minutes"


def _focus_text(context):
    count = context.get("metrics", {}).get("focus_session_count", 0)
    minutes = context.get("metrics", {}).get("focus_minutes", 0)
    if not count:
        return "no focus sessions captured"
    return f"{minutes} focus minutes across {count} session(s)"


def _blocker_text(blockers):
    if not blockers:
        return "No blockers captured"
    values = []
    for task in blockers:
        suffix = f" ({task['notes']})" if task.get("notes") else ""
        values.append(f"{task['title']}{suffix}")
    return "; ".join(values)


def _sentences(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if not value:
        return []
    text = str(value).replace("\n", " ").strip()
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


def _exactly_five(sentences):
    cleaned = [str(sentence).strip() for sentence in sentences if str(sentence).strip()]
    cleaned = [sentence if sentence.endswith((".", "!", "?")) else f"{sentence}." for sentence in cleaned]
    if len(cleaned) >= 5:
        return cleaned[:5]
    filler = [
        "I will keep the team posted if any risk changes.",
        "I am keeping the update focused on today's selected work.",
        "I will follow up after standup with any details that need discussion.",
    ]
    return (cleaned + filler)[:5]
