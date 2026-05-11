import json
import logging
from datetime import UTC, datetime

import oracledb
from fastapi import HTTPException

from db import get_connection
from repositories import task_repository
from repositories.task_enrichment_repository import ensure_schema as ensure_task_enrichment_schema
from services.api_cache import canonical_cache_key, get_cached_response, get_default_cache_ttl_seconds, invalidate_user_cache, set_cached_response
from services.task_ai_service import enrich_task_with_ai, fallback_task_enrichment
from services.user_context import parse_oracle_user_id
from services.xp_service import TSHIRT_ALLOWED, normalize_tshirt_size


TASK_LIST_CACHE_TTL_SECONDS = get_default_cache_ttl_seconds
TASK_LIST_CACHE_NAMESPACE = "task_list"
TASK_RELATED_CACHE_NAMESPACES = (
    TASK_LIST_CACHE_NAMESPACE,
    "dashboard_today",
    "insights_today",
    "quests_today",
    "quest_progress",
    "focus_sessions",
    "standup_note",
    "daily_overview",
    "weekly_overview",
)

VALID_TASK_TYPES = {"Task", "Bug", "Epic", "Review", "Meeting"}
VALID_SOURCES = {"Custom", "CUSTOM", "Jira", "Outlook"}
VALID_PRIORITIES = {"Critical", "High", "Medium", "Low"}
VALID_STATUSES = {"To Do", "In Progress", "Blocked", "Done", "Upcoming", "Cancelled"}
logger = logging.getLogger(__name__)

ALIASES = {
    "source": "external_source",
    "type": "task_type",
    "externalId": "external_id",
    "projectKey": "project_key",
    "dueDate": "due_at",
    "startDate": "start_at",
    "estimatedMinutes": "estimated_minutes",
    "actualMinutes": "actual_minutes",
    "xp": "xp_value",
    "workingToday": "working_today",
    "workedDates": "worked_dates",
    "runAiEnrichment": "run_ai_enrichment",
    "rowVersion": "row_version",
    "completedAt": "completed_at",
    "rcaTshirtSize": "rca_tshirt_size",
    "rcaFileChangeCount": "rca_file_change_count",
    "rcaComplexitySource": "rca_complexity_source",
    "rcaComplexityAt": "rca_complexity_at",
    "rcaReason": "rca_reason",
    "rcaAffectedFiles": "rca_affected_files",
    "rcaCodeSuggestion": "rca_code_suggestion",
    "rcaRawOutput": "rca_raw_output",
    "rcaTshirtJustification": "rca_tshirt_justification",
    "sourceEnrichmentJobId": "source_enrichment_job_id",
}


def list_oracle_tasks(filters=None, user_id=None):
    filters = dict(filters or {})
    work_date = _normalize_date(filters.get("worked_date") or _today_utc(), "worked_date")
    resolved_user_id = _user_id(user_id)
    cache_key = _task_list_cache_key(resolved_user_id, filters, work_date)
    cached = get_cached_response(TASK_LIST_CACHE_NAMESPACE, cache_key, TASK_LIST_CACHE_TTL_SECONDS())
    if cached:
        return cached
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        ensure_task_enrichment_schema(cur)
        response = task_repository.list_tasks(cur, resolved_user_id, filters, work_date)
        set_cached_response(TASK_LIST_CACHE_NAMESPACE, cache_key, response, user_id=resolved_user_id)
        return response
    except oracledb.DatabaseError as exc:
        raise HTTPException(status_code=503, detail="Task storage is unavailable.") from exc
    finally:
        if conn:
            conn.close()


def get_oracle_task(task_id, user_id=None):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        ensure_task_enrichment_schema(cur)
        task = task_repository.fetch_task(cur, _user_id(user_id), _task_id(task_id), _today_utc())
        if not task:
            _not_found()
        task["audit_events"] = task_repository.fetch_task_events(cur, _user_id(user_id), _task_id(task_id))
        return task
    except oracledb.DatabaseError as exc:
        raise HTTPException(status_code=503, detail="Task storage is unavailable.") from exc
    finally:
        if conn:
            conn.close()


def create_oracle_task(payload, user_id=None):
    task = _normalize_payload(payload)
    _validate_task_input(task)
    resolved_user_id = _user_id(user_id)
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        ensure_task_enrichment_schema(cur)
        _validate_unique_external_identity(cur, resolved_user_id, task)
        ai = enrich_task_with_ai(task) if task.get("run_ai_enrichment") else fallback_task_enrichment(task)
        task_id = task_repository.insert_task(cur, resolved_user_id, task, ai)
        worked_dates = _worked_dates_for_task(task)
        for work_date in worked_dates:
            task_repository.insert_work_date(cur, resolved_user_id, task_id, work_date, task.get("estimated_minutes"))
        task_repository.insert_task_event(cur, resolved_user_id, task_id, "TASK_CREATED", None, _event_payload(task, ai))
        conn.commit()
        _invalidate_task_related_caches(resolved_user_id)
        return task_repository.fetch_task(cur, resolved_user_id, task_id, _today_utc())
    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except oracledb.IntegrityError as exc:
        if conn:
            conn.rollback()
        logger.exception("Oracle integrity error while creating task for user_id=%s source=%s external_id=%s", _user_id(user_id), task.get("external_source"), task.get("external_id"))
        raise _integrity_error_http_exception(exc) from exc
    except oracledb.DatabaseError as exc:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=503, detail="Task storage is unavailable.") from exc
    finally:
        if conn:
            conn.close()


def update_oracle_task(task_id, payload, user_id=None):
    task_id = _task_id(task_id)
    data = _normalize_update_payload(payload)
    row_version = _optional_int((payload or {}).get("row_version") or (payload or {}).get("rowVersion"), "row_version")
    resolved_user_id = _user_id(user_id)
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        ensure_task_enrichment_schema(cur)
        existing = task_repository.fetch_task_for_update(cur, resolved_user_id, task_id)
        if not existing:
            _not_found()
        if row_version is not None and int(existing["row_version"]) != row_version:
            _conflict(existing["row_version"])
        existing_task = task_repository.fetch_task(cur, resolved_user_id, task_id, _today_utc())

        fields = _update_fields(data)
        if data.get("status") == "Done":
            fields.append(("COMPLETED_AT", "completed_at", data.get("completed_at") or datetime.now(UTC)))
        elif data.get("status") and data.get("status") != "Done":
            fields.append(("COMPLETED_AT", "completed_at", None))

        ai = None
        if _should_run_ai(payload):
            context_task = {**data, "priority": data.get("priority") or "Medium", "task_type": data.get("task_type") or "Task"}
            ai = enrich_task_with_ai(context_task)
            fields.extend(_ai_fields(ai))
        elif _should_refresh_derived_xp(data):
            context_task = _xp_refresh_context(existing_task, data)
            ai = fallback_task_enrichment(context_task)
            fields.extend(_ai_fields(ai))
            fields.append(("XP_VALUE", "xp_value", ai.get("xp_value")))

        work_date_change_requested = "worked_dates" in data or "working_today" in data
        if fields:
            ok = task_repository.update_task_fields(cur, resolved_user_id, task_id, fields, row_version)
        else:
            ok = task_repository.touch_task(cur, resolved_user_id, task_id, row_version) if work_date_change_requested else True
        if not ok:
            _conflict(existing["row_version"])

        if "worked_dates" in data:
            task_repository.sync_task_work_dates(cur, resolved_user_id, task_id, data["worked_dates"])
        if "working_today" in data:
            _set_work_date(cur, resolved_user_id, task_id, _today_utc(), bool(data["working_today"]))

        task_repository.insert_task_event(
            cur,
            resolved_user_id,
            task_id,
            "TASK_UPDATED",
            {"row_version": existing["row_version"]},
            {"fields": sorted(data), "ai_enriched": bool(ai)},
        )
        conn.commit()
        _invalidate_task_related_caches(resolved_user_id)
        return task_repository.fetch_task(cur, resolved_user_id, task_id, _today_utc())
    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except oracledb.DatabaseError as exc:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=503, detail="Task storage is unavailable.") from exc
    finally:
        if conn:
            conn.close()


def delete_oracle_task(task_id, user_id=None):
    task_id = _task_id(task_id)
    resolved_user_id = _user_id(user_id)
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        ensure_task_enrichment_schema(cur)
        existing = task_repository.fetch_task_for_update(cur, resolved_user_id, task_id)
        if not existing:
            _not_found()
        deleted = task_repository.delete_task(cur, resolved_user_id, task_id)
        if not deleted:
            _not_found()
        conn.commit()
        _invalidate_task_related_caches(resolved_user_id)
        return {"task_id": task_id, "id": str(task_id), "deleted": True}
    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except oracledb.DatabaseError as exc:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=503, detail="Task storage is unavailable.") from exc
    finally:
        if conn:
            conn.close()


def update_oracle_task_notes(task_id, payload, user_id=None):
    return update_oracle_task(task_id, {**dict(payload or {}), "notes": (payload or {}).get("notes", "")}, user_id)


def update_oracle_task_status(task_id, payload, user_id=None):
    data = dict(payload or {})
    if not data.get("status"):
        _validation_error("status is required.", {"field": "status"})
    task = update_oracle_task(task_id, data, user_id)
    if task["status"] == "Done":
        return _clear_today_after_completion(task_id, task, user_id, event_type="STATUS_CHANGED")
    return task


def complete_oracle_task(task_id, payload, user_id=None):
    data = dict(payload or {})
    notes = _append_notes(
        data.get("notes"),
        [data.get("completion_notes"), data.get("learnings"), data.get("went_well"), data.get("went_wrong")],
    )
    update_payload = {
        "row_version": data.get("row_version") or data.get("rowVersion"),
        "status": "Done",
        "actual_minutes": data.get("actual_minutes") or data.get("actualMinutes"),
        "notes": notes,
        "completed_at": _parse_datetime(data.get("completed_at") or data.get("completedAt")) or datetime.now(UTC),
    }
    task = update_oracle_task(task_id, update_payload, user_id)
    return _clear_today_after_completion(task_id, task, user_id, event_type="TASK_COMPLETED")


def update_oracle_task_today(task_id, payload, user_id=None):
    task_id = _task_id(task_id)
    data = _normalize_aliases(payload or {})
    requested = data.get("working_today")
    row_version = _optional_int(data.get("row_version"), "row_version")
    work_date = _normalize_date(data.get("work_date") or data.get("worked_date") or _today_utc(), "work_date")
    resolved_user_id = _user_id(user_id)
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        existing = task_repository.fetch_task_for_update(cur, resolved_user_id, task_id)
        if not existing:
            _not_found()
        if row_version is not None and int(existing["row_version"]) != row_version:
            _conflict(existing["row_version"])

        if requested is None:
            worked_dates = task_repository.list_worked_dates(cur, resolved_user_id, task_id)
            requested = work_date not in worked_dates
        requested = bool(requested) and existing["status"] != "Done"

        fields = []
        if requested and existing["status"] not in {"Blocked", "Done"}:
            fields.append(("STATUS", "status", "In Progress"))
            fields.append(("COMPLETED_AT", "completed_at", None))
        changed = _set_work_date(cur, resolved_user_id, task_id, work_date, requested)
        if fields or changed:
            ok = (
                task_repository.update_task_fields(cur, resolved_user_id, task_id, fields, row_version)
                if fields
                else task_repository.touch_task(cur, resolved_user_id, task_id, row_version)
            )
            if not ok:
                _conflict(existing["row_version"])
            task_repository.insert_task_event(
                cur,
                resolved_user_id,
                task_id,
                "WORKING_TODAY_UPDATED",
                {"work_date": work_date, "working_today": not requested},
                {"work_date": work_date, "working_today": requested},
            )
        conn.commit()
        _invalidate_task_related_caches(resolved_user_id)
        return task_repository.fetch_task(cur, resolved_user_id, task_id, work_date)
    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except oracledb.DatabaseError as exc:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=503, detail="Working-today storage is unavailable.") from exc
    finally:
        if conn:
            conn.close()


def _clear_today_after_completion(task_id, task, user_id, event_type):
    resolved_user_id = _user_id(user_id)
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        task_repository.delete_work_date(cur, resolved_user_id, _task_id(task_id), _today_utc())
        task_repository.insert_task_event(
            cur,
            resolved_user_id,
            _task_id(task_id),
            event_type,
            {},
            {"status": "Done", "completed_at": task.get("completed_at")},
        )
        conn.commit()
        _invalidate_task_related_caches(resolved_user_id)
        return task_repository.fetch_task(cur, resolved_user_id, _task_id(task_id), _today_utc())
    except oracledb.DatabaseError:
        if conn:
            conn.rollback()
        return task
    finally:
        if conn:
            conn.close()


def _set_work_date(cur, user_id, task_id, work_date, enabled):
    return (
        task_repository.insert_work_date(cur, user_id, task_id, work_date)
        if enabled
        else task_repository.delete_work_date(cur, user_id, task_id, work_date)
    )


def _task_list_cache_key(user_id, filters, work_date):
    return canonical_cache_key({
        "user_id": user_id,
        "work_date": work_date,
        "filters": filters,
    })


def _invalidate_task_related_caches(user_id):
    invalidate_user_cache(user_id, TASK_RELATED_CACHE_NAMESPACES)


def _normalize_payload(payload):
    data = _normalize_aliases(payload or {})
    data["title"] = _clean(data.get("title"))
    data["external_source"] = _clean(data.get("external_source")) or "Custom"
    data["external_id"] = _empty_to_none(data.get("external_id"))
    data["description"] = str(data.get("description") or "")
    data["task_type"] = _clean(data.get("task_type")) or "Task"
    data["priority"] = _clean(data.get("priority")) or "Medium"
    data["status"] = _clean(data.get("status")) or "To Do"
    data["project_key"] = _empty_to_none(data.get("project_key"))
    data["due_at"] = _parse_datetime(data.get("due_at"))
    data["start_at"] = _parse_datetime(data.get("start_at"))
    data["estimated_minutes"] = _optional_number(data.get("estimated_minutes"), "estimated_minutes")
    data["actual_minutes"] = _optional_number(data.get("actual_minutes"), "actual_minutes")
    data["rca_tshirt_size"] = _normalize_tshirt_size(data.get("rca_tshirt_size"))
    data["rca_file_change_count"] = _optional_number(data.get("rca_file_change_count"), "rca_file_change_count")
    data["rca_complexity_source"] = _empty_to_none(data.get("rca_complexity_source"))
    data["rca_complexity_at"] = _parse_datetime(data.get("rca_complexity_at"))
    data["rca_reason"] = _empty_to_none(data.get("rca_reason"))
    data["rca_affected_files"] = _labels(data.get("rca_affected_files"))
    data["rca_code_suggestion"] = _empty_to_none(data.get("rca_code_suggestion"))
    data["rca_raw_output"] = _empty_to_none(data.get("rca_raw_output"))
    data["rca_tshirt_justification"] = _empty_to_none(data.get("rca_tshirt_justification"))
    data["source_enrichment_job_id"] = _optional_int(data.get("source_enrichment_job_id"), "source_enrichment_job_id")
    data["xp_value"] = _optional_number(data.get("xp_value"), "xp_value")
    data["notes"] = str(data.get("notes") or "")
    data["labels"] = _labels(data.get("labels"))
    data["worked_dates"] = _dates(data.get("worked_dates"))
    if bool(data.get("working_today")) and data["status"] != "Done":
        data["worked_dates"] = sorted(set(data["worked_dates"] + [_today_utc()]))
        if data["status"] != "Blocked":
            data["status"] = "In Progress"
    _normalize_custom_source_identity(data)
    data["run_ai_enrichment"] = bool(data.get("run_ai_enrichment", True))
    return data


def _normalize_update_payload(payload):
    raw = _normalize_aliases(payload or {})
    if raw.get("xp_value") in (None, ""):
        raw.pop("xp_value", None)
    data = {}
    for field in (
        "title",
        "description",
        "external_source",
        "external_id",
        "task_type",
        "priority",
        "status",
        "project_key",
        "due_at",
        "start_at",
        "estimated_minutes",
        "actual_minutes",
        "rca_tshirt_size",
        "rca_file_change_count",
        "rca_complexity_source",
        "rca_complexity_at",
        "rca_reason",
        "rca_affected_files",
        "rca_code_suggestion",
        "rca_raw_output",
        "rca_tshirt_justification",
        "source_enrichment_job_id",
        "xp_value",
        "notes",
        "labels",
        "worked_dates",
        "working_today",
        "completed_at",
    ):
        if field in raw:
            data[field] = raw[field]
    if "title" in data:
        data["title"] = _clean(data["title"])
        if not data["title"]:
            _validation_error("title cannot be empty.", {"field": "title"})
    for field in ("external_source", "task_type", "priority", "status", "project_key", "external_id"):
        if field in data:
            data[field] = _empty_to_none(data[field]) if field in {"project_key", "external_id"} else _clean(data[field])
    for field in ("due_at", "start_at", "completed_at", "rca_complexity_at"):
        if field in data:
            data[field] = _parse_datetime(data[field])
    for field in ("estimated_minutes", "actual_minutes", "xp_value", "rca_file_change_count"):
        if field in data:
            data[field] = _optional_number(data[field], field)
    if "source_enrichment_job_id" in data:
        data["source_enrichment_job_id"] = _optional_int(data["source_enrichment_job_id"], "source_enrichment_job_id")
    if "rca_tshirt_size" in data:
        data["rca_tshirt_size"] = _normalize_tshirt_size(data["rca_tshirt_size"])
    if "labels" in data:
        data["labels"] = _labels(data["labels"])
    if "rca_affected_files" in data:
        data["rca_affected_files"] = _labels(data["rca_affected_files"])
    if "worked_dates" in data:
        data["worked_dates"] = _dates(data["worked_dates"])
    if "working_today" in data:
        data["working_today"] = bool(data["working_today"])
    _normalize_custom_source_identity(data)
    _validate_update_data(data)
    return data


def _update_fields(data):
    mapping = {
        "title": "TITLE",
        "description": "DESCRIPTION",
        "external_source": "EXTERNAL_SOURCE",
        "external_id": "EXTERNAL_ID",
        "task_type": "TASK_TYPE",
        "priority": "PRIORITY",
        "status": "STATUS",
        "project_key": "PROJECT_KEY",
        "due_at": "DUE_DATE",
        "start_at": "START_DATE",
        "estimated_minutes": "ESTIMATED_MINUTES",
        "actual_minutes": "ACTUAL_MINUTES",
        "rca_tshirt_size": "RCA_TSHIRT_SIZE",
        "rca_file_change_count": "RCA_FILE_CHANGE_COUNT",
        "rca_complexity_source": "RCA_COMPLEXITY_SOURCE",
        "rca_complexity_at": "RCA_COMPLEXITY_AT",
        "rca_reason": "RCA_REASON",
        "rca_affected_files": "RCA_AFFECTED_FILES_JSON",
        "rca_code_suggestion": "RCA_CODE_SUGGESTION",
        "rca_raw_output": "RCA_RAW_OUTPUT",
        "rca_tshirt_justification": "RCA_TSHIRT_JUSTIFICATION",
        "source_enrichment_job_id": "SOURCE_ENRICHMENT_JOB_ID",
        "xp_value": "XP_VALUE",
        "notes": "NOTES",
        "labels": "LABELS_JSON",
    }
    fields = []
    for key, column in mapping.items():
        if key not in data:
            continue
        value = json.dumps(data[key], separators=(",", ":")) if key in {"labels", "rca_affected_files"} else data[key]
        fields.append((column, key, value))
    return fields


def _ai_fields(ai):
    return [
        ("AI_DIFFICULTY", "ai_difficulty", ai.get("difficulty")),
        ("AI_IMPACT_SCORE", "ai_impact_score", ai.get("impact_score")),
        ("AI_PRIORITY_SCORE", "ai_priority_score", ai.get("priority_score")),
        ("AI_EFFORT_MINUTES", "ai_effort_minutes", ai.get("effort_minutes")),
        ("AI_CATEGORY", "ai_category", ai.get("category")),
        ("AI_INSIGHT", "ai_insight", ai.get("insight")),
        ("AI_MODEL_VERSION", "ai_model_version", ai.get("model_id")),
        ("AI_ENRICHED_AT", "ai_enriched_at", datetime.now(UTC)),
    ]


def _validate_task_input(data):
    missing = [field for field in ("title", "task_type", "external_source", "priority", "status") if not data.get(field)]
    if missing:
        _validation_error("Missing required field(s).", {"fields": missing})
    _validate_update_data(data)


def _validate_update_data(data):
    if data.get("task_type") and data["task_type"] not in VALID_TASK_TYPES:
        _validation_error("Invalid task_type.", {"field": "task_type", "allowed": sorted(VALID_TASK_TYPES), "received": data["task_type"]})
    if data.get("external_source") and data["external_source"] not in VALID_SOURCES:
        _validation_error("Invalid external_source.", {"field": "external_source", "allowed": sorted(VALID_SOURCES), "received": data["external_source"]})
    if data.get("priority") and data["priority"] not in VALID_PRIORITIES:
        _validation_error("Invalid priority.", {"field": "priority", "allowed": sorted(VALID_PRIORITIES), "received": data["priority"]})
    if data.get("status") and data["status"] not in VALID_STATUSES:
        _validation_error("Invalid status.", {"field": "status", "allowed": sorted(VALID_STATUSES), "received": data["status"]})
    for field in ("estimated_minutes", "actual_minutes", "xp_value", "rca_file_change_count"):
        if data.get(field) is not None and data[field] < 0:
            _validation_error(f"{field} cannot be negative.", {"field": field})


def _validate_unique_external_identity(cur, user_id, task):
    external_id = task.get("external_id")
    if not external_id:
        return
    cur.execute(
        """
        SELECT 1
        FROM WORK_ITEMS
        WHERE USER_ID = :user_id
          AND EXTERNAL_SOURCE = :external_source
          AND EXTERNAL_ID = :external_id
        FETCH FIRST 1 ROWS ONLY
        """,
        {"user_id": user_id, "external_source": task["external_source"], "external_id": external_id},
    )
    if cur.fetchone():
        raise HTTPException(
            status_code=409,
            detail={"code": "DUPLICATE_EXTERNAL_TASK", "message": "A task with this external_source and external_id already exists."},
        )


def _worked_dates_for_task(task):
    return _dates(task.get("worked_dates"))


def _normalize_aliases(payload):
    data = dict(payload or {})
    for alias, canonical in ALIASES.items():
        if canonical not in data and alias in data:
            data[canonical] = data[alias]
    if "is_working_today" in data and "working_today" not in data:
        data["working_today"] = data["is_working_today"]
    return data


def _normalize_tshirt_size(value):
    if value in (None, ""):
        return None
    size = normalize_tshirt_size(value)
    if size not in TSHIRT_ALLOWED:
        _validation_error("rca_tshirt_size must be one of XS, S, M, L, XL, NA.", {"field": "rca_tshirt_size"})
    return size


def _labels(value):
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _dates(value):
    if value in (None, ""):
        return []
    raw = value if isinstance(value, list) else str(value).split(",")
    return sorted({_normalize_date(item, "worked_dates") for item in raw if str(item).strip()})


def _normalize_custom_source_identity(data):
    if data.get("external_source") in {"Custom", "CUSTOM"}:
        # User-created tasks are first-party rows, not synced external records.
        data["external_id"] = None


def _integrity_error_http_exception(exc):
    error = exc.args[0] if exc.args else None
    code = getattr(error, "code", None)
    message = str(getattr(error, "message", "") or str(exc))

    if code == 1:
        return HTTPException(
            status_code=409,
            detail={"code": "DUPLICATE_EXTERNAL_TASK", "message": "A task with this external source and ID already exists."},
        )

    if code == 2291:
        return HTTPException(
            status_code=403,
            detail={
                "code": "USER_NOT_PROVISIONED",
                "message": "This user is not provisioned in the Oracle APP_USERS table yet. The current auth flow is still using a local user id that does not exist in the DB.",
            },
        )

    return HTTPException(
        status_code=409,
        detail={"code": "TASK_CONSTRAINT_VIOLATION", "message": "Task data violated an Oracle integrity constraint."},
    )


def _normalize_date(value, field):
    text = _empty_to_none(value)
    if not text:
        _validation_error(f"{field} is required.", {"field": field})
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        _validation_error(f"{field} must use YYYY-MM-DD format.", {"field": field, "received": value})
    return text


def _parse_datetime(value):
    text = _empty_to_none(value)
    if not text:
        return None
    try:
        if len(text) == 10:
            return datetime.strptime(text, "%Y-%m-%d")
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        _validation_error("datetime fields must use ISO format.", {"received": value})


def _optional_number(value, field):
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        _validation_error(f"{field} must be a number.", {"field": field})
    return int(number) if number.is_integer() else number


def _optional_int(value, field):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        _validation_error(f"{field} must be an integer.", {"field": field})


def _user_id(value):
    return parse_oracle_user_id(value)


def _task_id(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        _validation_error("task_id must be numeric.", {"field": "task_id", "received": value})


def _today_utc():
    return datetime.now(UTC).date().isoformat()


def _clean(value):
    return None if value is None else str(value).strip()


def _empty_to_none(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _append_notes(first, additions):
    parts = [str(first).strip()] if first and str(first).strip() else []
    parts.extend(str(item).strip() for item in additions if item and str(item).strip())
    return "\n\n".join(parts)


def _event_payload(task, ai):
    return {"task": {k: v for k, v in task.items() if k != "notes"}, "ai": ai}


def _should_run_ai(payload):
    data = _normalize_aliases(payload or {})
    return bool(data.get("run_ai_enrichment"))


def _should_refresh_derived_xp(data):
    if "xp_value" in data:
        return False
    return any(
        field in data
        for field in ("priority", "task_type", "estimated_minutes", "rca_tshirt_size", "rca_file_change_count")
    )


def _xp_refresh_context(existing_task, data):
    return {
        "title": data.get("title", existing_task.get("title")),
        "description": data.get("description", existing_task.get("description")),
        "task_type": data.get("task_type", existing_task.get("task_type")),
        "priority": data.get("priority", existing_task.get("priority")),
        "status": data.get("status", existing_task.get("status")),
        "estimated_minutes": data.get("estimated_minutes", existing_task.get("estimated_minutes")),
        "actual_minutes": data.get("actual_minutes", existing_task.get("actual_minutes")),
        "rca_tshirt_size": data.get("rca_tshirt_size", existing_task.get("rca_tshirt_size")),
        "rca_file_change_count": data.get("rca_file_change_count", existing_task.get("rca_file_change_count")),
        "notes": data.get("notes", existing_task.get("notes")),
        "labels": data.get("labels", existing_task.get("labels")),
        "xp_value": None,
    }


def _not_found():
    raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "Task was not found."})


def _conflict(current_row_version):
    raise HTTPException(
        status_code=409,
        detail={
            "code": "ROW_VERSION_CONFLICT",
            "message": "Task was updated by another request.",
            "current_row_version": current_row_version,
        },
    )


def _validation_error(message, details):
    raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": message, "details": details})
