from datetime import datetime, timezone

from fastapi import HTTPException

from services.filesystem_store import read_records, with_store_lock, write_records


WORK_ITEMS_FILE = "work_items.json"
WORK_ITEM_EVENTS_FILE = "work_item_events.json"
DAILY_WORK_ITEMS_FILE = "daily_work_items.json"
AI_RUNS_FILE = "ai_runs.json"
LOCAL_USER_ID = "local-user"

VALID_TASK_TYPES = {"Task", "Bug", "Epic", "Review", "Meeting"}
VALID_SOURCES = {"Custom", "Jira", "Outlook", "Microsoft To Do"}
VALID_PRIORITIES = {"Critical", "High", "Medium", "Low"}
VALID_STATUSES = {"To Do", "In Progress", "Blocked", "Done", "Upcoming"}

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
}


def create_filesystem_task(payload, user_id=LOCAL_USER_ID):
    def action():
        tasks = read_records(WORK_ITEMS_FILE)
        events = read_records(WORK_ITEM_EVENTS_FILE)
        daily_items = read_records(DAILY_WORK_ITEMS_FILE)
        ai_runs = read_records(AI_RUNS_FILE)

        task_input = _normalize_payload(payload)
        _validate_task_input(task_input)
        _validate_unique_external_identity(tasks, task_input, user_id)

        now = _now_iso()
        task_id = _next_id(tasks, "task_id")
        task = {
            "task_id": task_id,
            "id": str(task_id),
            "user_id": user_id,
            "external_source": task_input["external_source"],
            "external_id": task_input.get("external_id"),
            "title": task_input["title"],
            "description": task_input.get("description") or "",
            "task_type": task_input["task_type"],
            "priority": task_input["priority"],
            "status": task_input["status"],
            "project_key": task_input.get("project_key"),
            "due_at": task_input.get("due_at"),
            "start_at": task_input.get("start_at"),
            "estimated_minutes": task_input.get("estimated_minutes"),
            "actual_minutes": task_input.get("actual_minutes"),
            "xp_value": task_input.get("xp_value"),
            "notes": task_input.get("notes") or "",
            "labels": task_input.get("labels") or [],
            "worked_dates": task_input.get("worked_dates") or "",
            "working_today": task_input.get("working_today", False),
            "run_ai_enrichment": task_input.get("run_ai_enrichment", False),
            "row_version": 1,
            "created_at": now,
            "updated_at": now,
            "completed_at": now if task_input["status"] == "Done" else None,
        }

        if task["run_ai_enrichment"]:
            ai_run = _create_ai_run(ai_runs, task, now)
            task.update(_build_ai_fields(task))
            task["ai_run_id"] = ai_run["ai_run_id"]

        task = _with_frontend_aliases(task)
        tasks.append(task)
        events.append(_create_event(events, task, now))

        if task["working_today"]:
            _upsert_daily_work_item(daily_items, task, now)

        write_records(WORK_ITEMS_FILE, tasks)
        write_records(WORK_ITEM_EVENTS_FILE, events)
        write_records(DAILY_WORK_ITEMS_FILE, daily_items)
        write_records(AI_RUNS_FILE, ai_runs)

        return _response_task(task)

    return with_store_lock(action)


def list_filesystem_tasks(filters=None, user_id=LOCAL_USER_ID):
    def action():
        filters_data = filters or {}
        tasks = read_records(WORK_ITEMS_FILE)
        filtered_tasks = _filter_tasks(tasks, filters_data, user_id)
        page = _positive_int(filters_data.get("page"), "page", 1)
        page_size = _positive_int(filters_data.get("page_size"), "page_size", 50)
        page_size = min(page_size, 100)
        total = len(filtered_tasks)
        start = (page - 1) * page_size
        end = start + page_size
        return {
            "items": [_response_task(task, filters_data.get("worked_date")) for task in filtered_tasks[start:end]],
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": end < total,
        }

    return with_store_lock(action)


def get_filesystem_task(task_id, user_id=LOCAL_USER_ID):
    def action():
        tasks = read_records(WORK_ITEMS_FILE)
        events = read_records(WORK_ITEM_EVENTS_FILE)
        task = _require_task(tasks, task_id, user_id)

        task_detail = _response_task(task)
        task_events = [
            event
            for event in events
            if str(event.get("task_id")) == str(task_detail.get("task_id"))
            and event.get("user_id") == user_id
        ]
        task_detail["audit_events"] = sorted(task_events, key=lambda event: event.get("created_at") or "")
        return task_detail

    return with_store_lock(action)


def update_filesystem_task_today(task_id, payload, user_id=LOCAL_USER_ID):
    def action():
        tasks = read_records(WORK_ITEMS_FILE)
        events = read_records(WORK_ITEM_EVENTS_FILE)
        daily_items = read_records(DAILY_WORK_ITEMS_FILE)

        task = _require_task(tasks, task_id, user_id)

        now = _now_iso()
        work_date = _extract_work_date(payload, now)
        requested_value = _extract_working_today(payload, task, work_date)
        worked_dates = _task_worked_dates(task)
        if requested_value:
            worked_dates = _add_worked_date(worked_dates, work_date)
        else:
            worked_dates = [date for date in worked_dates if date != work_date]
        task["worked_dates"] = _worked_dates_to_storage(worked_dates)
        task["working_today"] = requested_value
        task["workingToday"] = requested_value
        task["updated_at"] = now
        task["row_version"] = int(task.get("row_version") or 1) + 1

        daily_item = _upsert_daily_work_item(daily_items, task, now, requested_value, work_date)
        events.append(_create_today_event(events, task, daily_item, now))

        write_records(WORK_ITEMS_FILE, tasks)
        write_records(DAILY_WORK_ITEMS_FILE, daily_items)
        write_records(WORK_ITEM_EVENTS_FILE, events)

        return _response_task(task, work_date)

    return with_store_lock(action)


def update_filesystem_task(task_id, payload, user_id=LOCAL_USER_ID):
    def action():
        tasks = read_records(WORK_ITEMS_FILE)
        events = read_records(WORK_ITEM_EVENTS_FILE)
        ai_runs = read_records(AI_RUNS_FILE)
        task = _require_task(tasks, task_id, user_id)
        _validate_row_version(task, payload)

        update_data = _normalize_update_payload(payload)
        _apply_task_updates(task, update_data)
        now = _now_iso()
        _finish_task_update(task, now)

        if _should_run_ai(payload):
            ai_run = _create_ai_run(ai_runs, task, now)
            task.update(_build_ai_fields(task))
            task["ai_run_id"] = ai_run["ai_run_id"]

        updated_task = _response_task(task)
        events.append(_create_change_event(events, updated_task, "TASK_UPDATED", now, {"fields": sorted(update_data)}))

        write_records(WORK_ITEMS_FILE, tasks)
        write_records(WORK_ITEM_EVENTS_FILE, events)
        write_records(AI_RUNS_FILE, ai_runs)
        return updated_task

    return with_store_lock(action)


def update_filesystem_task_notes(task_id, payload, user_id=LOCAL_USER_ID):
    def action():
        tasks = read_records(WORK_ITEMS_FILE)
        events = read_records(WORK_ITEM_EVENTS_FILE)
        ai_runs = read_records(AI_RUNS_FILE)
        task = _require_task(tasks, task_id, user_id)
        _validate_row_version(task, payload)

        now = _now_iso()
        task["notes"] = _empty_to_default((payload or {}).get("notes"), "")
        _finish_task_update(task, now)

        if _should_run_ai(payload):
            ai_run = _create_ai_run(ai_runs, task, now)
            task.update(_build_ai_fields(task))
            task["ai_run_id"] = ai_run["ai_run_id"]

        updated_task = _response_task(task)
        events.append(_create_change_event(events, updated_task, "NOTES_UPDATED", now, {"notes": task["notes"]}))

        write_records(WORK_ITEMS_FILE, tasks)
        write_records(WORK_ITEM_EVENTS_FILE, events)
        write_records(AI_RUNS_FILE, ai_runs)
        return updated_task

    return with_store_lock(action)


def update_filesystem_task_status(task_id, payload, user_id=LOCAL_USER_ID):
    def action():
        tasks = read_records(WORK_ITEMS_FILE)
        events = read_records(WORK_ITEM_EVENTS_FILE)
        task = _require_task(tasks, task_id, user_id)
        if (payload or {}).get("row_version") is not None:
            _validate_row_version(task, payload)

        data = dict(payload or {})
        status = _clean_string(data.get("status"))
        _validate_enum("status", status, VALID_STATUSES)
        now = _now_iso()
        task["status"] = status
        if "actual_minutes" in data or "actualMinutes" in data:
            task["actual_minutes"] = _optional_number(data.get("actual_minutes", data.get("actualMinutes")), "actual_minutes")
        if data.get("notes"):
            task["notes"] = _append_notes(task.get("notes") or "", [data.get("notes")])
        if status == "Done" and not task.get("completed_at"):
            task["completed_at"] = now
        elif status != "Done":
            task["completed_at"] = None
        _finish_task_update(task, now)

        updated_task = _response_task(task)
        events.append(_create_change_event(events, updated_task, "STATUS_CHANGED", now, {"status": status}))

        write_records(WORK_ITEMS_FILE, tasks)
        write_records(WORK_ITEM_EVENTS_FILE, events)
        return updated_task

    return with_store_lock(action)


def complete_filesystem_task(task_id, payload, user_id=LOCAL_USER_ID):
    def action():
        tasks = read_records(WORK_ITEMS_FILE)
        events = read_records(WORK_ITEM_EVENTS_FILE)
        task = _require_task(tasks, task_id, user_id)
        _validate_row_version(task, payload)

        data = dict(payload or {})
        now = _now_iso()
        completed_at = _empty_to_none(data.get("completed_at") or data.get("completedAt")) or now
        task["status"] = "Done"
        task["completed_at"] = completed_at
        if "actual_minutes" in data or "actualMinutes" in data:
            task["actual_minutes"] = _optional_number(data.get("actual_minutes", data.get("actualMinutes")), "actual_minutes")
        task["notes"] = _append_notes(
            task.get("notes") or "",
            [
                data.get("notes"),
                data.get("completion_notes"),
                data.get("learnings"),
                data.get("went_well"),
                data.get("went_wrong"),
            ],
        )
        if task.get("xp_value") is None:
            task.update(_build_ai_fields(task))
        _finish_task_update(task, now)

        updated_task = _response_task(task)
        events.append(
            _create_change_event(
                events,
                updated_task,
                "TASK_COMPLETED",
                now,
                {"completed_at": completed_at, "summaries_stale": True},
            )
        )

        write_records(WORK_ITEMS_FILE, tasks)
        write_records(WORK_ITEM_EVENTS_FILE, events)
        return updated_task

    return with_store_lock(action)


def _filter_tasks(tasks, filters, user_id):
    results = [task for task in tasks if task.get("user_id") == user_id]
    status_values = _filter_values(filters.get("status"))
    source_values = _filter_values(filters.get("source") or filters.get("external_source"))
    priority_values = _filter_values(filters.get("priority"))
    working_today = filters.get("working_today")
    worked_date = _normalize_date(_empty_to_none(filters.get("worked_date")) or _today_key(_now_iso()), "worked_date")
    completed_date = _empty_to_none(filters.get("completed_date"))
    completed_from = _empty_to_none(filters.get("completed_from"))
    completed_to = _empty_to_none(filters.get("completed_to"))
    search = _empty_to_none(filters.get("search") or filters.get("q"))

    if status_values:
        results = [task for task in results if task.get("status") in status_values]
    if source_values:
        results = [task for task in results if task.get("external_source") in source_values or task.get("source") in source_values]
    if priority_values:
        results = [task for task in results if task.get("priority") in priority_values]
    if working_today is not None:
        results = [task for task in results if _has_worked_date(task, worked_date) is bool(working_today)]
    if filters.get("worked_date"):
        results = [task for task in results if _has_worked_date(task, worked_date)]
    if completed_date:
        results = [task for task in results if _date_part(task.get("completed_at") or task.get("completedAt")) == completed_date]
    if completed_from:
        results = [task for task in results if _date_or_empty(task.get("completed_at") or task.get("completedAt")) >= completed_from]
    if completed_to:
        results = [task for task in results if _date_or_empty(task.get("completed_at") or task.get("completedAt")) <= completed_to]
    if search:
        needle = search.lower()
        results = [
            task
            for task in results
            if needle in " ".join(
                [
                    str(task.get("title") or ""),
                    str(task.get("description") or ""),
                    str(task.get("notes") or ""),
                ]
            ).lower()
        ]

    return sorted(results, key=lambda task: task.get("created_at") or "", reverse=True)


def _normalize_payload(payload):
    data = dict(payload or {})
    for alias, canonical in ALIASES.items():
        if canonical not in data and alias in data:
            data[canonical] = data[alias]

    data["title"] = _clean_string(data.get("title"))
    data["external_source"] = _clean_string(data.get("external_source"))
    data["external_id"] = _empty_to_none(data.get("external_id"))
    data["description"] = _empty_to_default(data.get("description"), "")
    data["task_type"] = _clean_string(data.get("task_type"))
    data["priority"] = _clean_string(data.get("priority"))
    data["status"] = _clean_string(data.get("status"))
    data["project_key"] = _empty_to_none(data.get("project_key"))
    data["due_at"] = _empty_to_none(data.get("due_at"))
    data["start_at"] = _empty_to_none(data.get("start_at"))
    data["estimated_minutes"] = _optional_number(data.get("estimated_minutes"), "estimated_minutes")
    data["actual_minutes"] = _optional_number(data.get("actual_minutes"), "actual_minutes")
    data["xp_value"] = _optional_number(data.get("xp_value"), "xp_value")
    data["notes"] = _empty_to_default(data.get("notes"), "")
    data["labels"] = _normalize_labels(data.get("labels"))
    worked_dates = _normalize_worked_dates(data.get("worked_dates"))
    if bool(data.get("working_today", False)):
        worked_dates = _add_worked_date(worked_dates, _today_key(_now_iso()))
    data["worked_dates"] = _worked_dates_to_storage(worked_dates)
    data["working_today"] = _today_key(_now_iso()) in worked_dates
    data["run_ai_enrichment"] = bool(data.get("run_ai_enrichment", False))
    return data


def _normalize_update_payload(payload):
    raw = dict(payload or {})
    for alias, canonical in ALIASES.items():
        if canonical not in raw and alias in raw:
            raw[canonical] = raw[alias]

    allowed = {
        "title",
        "description",
        "task_type",
        "priority",
        "status",
        "project_key",
        "due_at",
        "start_at",
        "estimated_minutes",
        "actual_minutes",
        "xp_value",
        "notes",
        "labels",
        "worked_dates",
    }
    data = {field: raw[field] for field in allowed if field in raw}

    if "title" in data:
        data["title"] = _clean_string(data["title"])
        if not data["title"]:
            _validation_error("title cannot be empty.", {"field": "title"})
    if "description" in data:
        data["description"] = _empty_to_default(data["description"], "")
    if "task_type" in data:
        data["task_type"] = _clean_string(data["task_type"])
        _validate_enum("task_type", data["task_type"], VALID_TASK_TYPES)
    if "priority" in data:
        data["priority"] = _clean_string(data["priority"])
        _validate_enum("priority", data["priority"], VALID_PRIORITIES)
    if "status" in data:
        data["status"] = _clean_string(data["status"])
        _validate_enum("status", data["status"], VALID_STATUSES)
    if "project_key" in data:
        data["project_key"] = _empty_to_none(data["project_key"])
    if "due_at" in data:
        data["due_at"] = _empty_to_none(data["due_at"])
    if "start_at" in data:
        data["start_at"] = _empty_to_none(data["start_at"])
    for field in ("estimated_minutes", "actual_minutes", "xp_value"):
        if field in data:
            data[field] = _optional_number(data[field], field)
            if data[field] is not None and data[field] < 0:
                _validation_error(f"{field} cannot be negative.", {"field": field})
    if "notes" in data:
        data["notes"] = _empty_to_default(data["notes"], "")
    if "labels" in data:
        data["labels"] = _normalize_labels(data["labels"])
    if "worked_dates" in data:
        data["worked_dates"] = _worked_dates_to_storage(_normalize_worked_dates(data["worked_dates"]))
    return data


def _apply_task_updates(task, update_data):
    for field, value in update_data.items():
        task[field] = value
    if "worked_dates" in update_data:
        task["working_today"] = _has_worked_date(task, _today_key(_now_iso()))
    if "status" in update_data:
        if update_data.get("status") == "Done" and not task.get("completed_at"):
            task["completed_at"] = _now_iso()
        elif update_data.get("status") != "Done":
            task["completed_at"] = None


def _finish_task_update(task, now):
    task["updated_at"] = now
    task["row_version"] = int(task.get("row_version") or 1) + 1
    _with_frontend_aliases(task)


def _require_task(tasks, task_id, user_id):
    task = _find_task(tasks, task_id)
    if task is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "TASK_NOT_FOUND", "message": "Task was not found."},
        )
    if task.get("user_id") != user_id:
        raise HTTPException(
            status_code=403,
            detail={"code": "TASK_FORBIDDEN", "message": "Task does not belong to the current user."},
        )
    return task


def _validate_row_version(task, payload):
    data = dict(payload or {})
    if data.get("row_version") is None and data.get("rowVersion") is None:
        _validation_error("row_version is required.", {"field": "row_version"})
    provided = data.get("row_version", data.get("rowVersion"))
    try:
        provided = int(provided)
    except (TypeError, ValueError):
        _validation_error("row_version must be an integer.", {"field": "row_version"})
    current = int(task.get("row_version") or 1)
    if provided != current:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ROW_VERSION_CONFLICT",
                "message": "Task was updated by another request.",
                "current_row_version": current,
            },
        )


def _should_run_ai(payload):
    data = dict(payload or {})
    return bool(data.get("run_ai_enrichment") or data.get("runAiEnrichment"))


def _filter_values(value):
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _positive_int(value, field, default):
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        _validation_error(f"{field} must be a positive integer.", {"field": field})
    if parsed < 1:
        _validation_error(f"{field} must be a positive integer.", {"field": field})
    return parsed


def _date_part(value):
    if not value:
        return ""
    return str(value)[:10]


def _date_or_empty(value):
    return _date_part(value)


def _validate_task_input(data):
    missing = [
        field
        for field in ("title", "task_type", "external_source", "priority", "status")
        if not data.get(field)
    ]
    if missing:
        _validation_error("Missing required field(s).", {"fields": missing})

    _validate_enum("task_type", data["task_type"], VALID_TASK_TYPES)
    _validate_enum("external_source", data["external_source"], VALID_SOURCES)
    _validate_enum("priority", data["priority"], VALID_PRIORITIES)
    _validate_enum("status", data["status"], VALID_STATUSES)

    for field in ("estimated_minutes", "actual_minutes", "xp_value"):
        value = data.get(field)
        if value is not None and value < 0:
            _validation_error(f"{field} cannot be negative.", {"field": field})


def _validate_unique_external_identity(tasks, data, user_id):
    external_id = data.get("external_id")
    if not external_id:
        return

    for task in tasks:
        if (
            task.get("user_id") == user_id
            and task.get("external_source") == data["external_source"]
            and task.get("external_id") == external_id
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "DUPLICATE_EXTERNAL_TASK",
                    "message": "A task with this external_source and external_id already exists.",
                },
            )


def _validate_enum(field, value, allowed):
    if value not in allowed:
        _validation_error(
            f"Invalid {field}.",
            {"field": field, "allowed": sorted(allowed), "received": value},
        )


def _validation_error(message, details):
    raise HTTPException(
        status_code=422,
        detail={"code": "VALIDATION_ERROR", "message": message, "details": details},
    )


def _clean_string(value):
    if value is None:
        return None
    return str(value).strip()


def _empty_to_none(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _empty_to_default(value, default):
    if value is None:
        return default
    return str(value)


def _optional_number(value, field):
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        _validation_error(f"{field} must be a number.", {"field": field})
    if number.is_integer():
        return int(number)
    return number


def _normalize_labels(value):
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _normalize_worked_dates(value):
    if value in (None, ""):
        return []
    if isinstance(value, list):
        raw_dates = value
    else:
        raw_dates = str(value).split(",")
    return sorted({_normalize_date(date, "worked_dates") for date in raw_dates if str(date).strip()})


def _normalize_date(value, field):
    text = _empty_to_none(value)
    if not text:
        _validation_error(f"{field} is required.", {"field": field})
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        _validation_error(f"{field} must use YYYY-MM-DD format.", {"field": field, "received": value})
    return text


def _worked_dates_to_storage(worked_dates):
    return ",".join(sorted(worked_dates))


def _task_worked_dates(task):
    worked_dates = _normalize_worked_dates(task.get("worked_dates"))
    if not worked_dates and bool(task.get("working_today") or task.get("workingToday")):
        worked_dates = [_today_key(_now_iso())]
    return worked_dates


def _has_worked_date(task, worked_date):
    return worked_date in _task_worked_dates(task)


def _add_worked_date(worked_dates, worked_date):
    return sorted(set(worked_dates + [_normalize_date(worked_date, "worked_date")]))


def _extract_work_date(payload, now):
    data = dict(payload or {})
    return _normalize_date(
        data.get("work_date") or data.get("workDate") or data.get("worked_date") or data.get("workedDate") or _today_key(now),
        "work_date",
    )


def _next_id(records, id_field):
    ids = [record.get(id_field, 0) for record in records if isinstance(record.get(id_field), int)]
    return max(ids, default=0) + 1


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _today_key(now):
    return now[:10]


def _create_event(events, task, now):
    return {
        "event_id": _next_id(events, "event_id"),
        "task_id": task["task_id"],
        "user_id": task["user_id"],
        "event_type": "TASK_CREATED",
        "created_at": now,
        "payload": task,
    }


def _find_task(tasks, task_id):
    task_id_text = str(task_id)
    for task in tasks:
        if str(task.get("task_id")) == task_id_text or str(task.get("id")) == task_id_text:
            return task
    return None


def _extract_working_today(payload, task, work_date=None):
    data = dict(payload or {})
    if "working_today" in data:
        return bool(data["working_today"])
    if "workingToday" in data:
        return bool(data["workingToday"])
    if "is_working_today" in data:
        return bool(data["is_working_today"])
    if "isWorkingToday" in data:
        return bool(data["isWorkingToday"])
    return not _has_worked_date(task, work_date or _today_key(_now_iso()))


def _upsert_daily_work_item(daily_items, task, now, is_working_today=True, work_date=None):
    work_date = work_date or _today_key(now)
    for item in daily_items:
        if (
            item.get("user_id") == task["user_id"]
            and item.get("task_id") == task["task_id"]
            and item.get("work_date") == work_date
        ):
            item.update({"is_working_today": is_working_today, "updated_at": now})
            return item

    item = {
        "daily_work_item_id": _next_id(daily_items, "daily_work_item_id"),
        "task_id": task["task_id"],
        "user_id": task["user_id"],
        "work_date": work_date,
        "is_working_today": is_working_today,
        "created_at": now,
        "updated_at": now,
    }
    daily_items.append(item)
    return item


def _create_today_event(events, task, daily_item, now):
    return {
        "event_id": _next_id(events, "event_id"),
        "task_id": task["task_id"],
        "user_id": task["user_id"],
        "event_type": "WORKING_TODAY_CHANGED",
        "created_at": now,
        "payload": {
            "task_id": task["task_id"],
            "working_today": task["working_today"],
            "daily_work_item_id": daily_item["daily_work_item_id"],
            "work_date": daily_item["work_date"],
        },
    }


def _create_change_event(events, task, event_type, now, payload):
    return {
        "event_id": _next_id(events, "event_id"),
        "task_id": task["task_id"],
        "user_id": task["user_id"],
        "event_type": event_type,
        "created_at": now,
        "payload": payload,
    }


def _append_notes(existing_notes, additions):
    parts = [existing_notes.strip()] if existing_notes and existing_notes.strip() else []
    parts.extend(str(item).strip() for item in additions if item and str(item).strip())
    return "\n\n".join(parts)


def _create_ai_run(ai_runs, task, now):
    ai_run = {
        "ai_run_id": _next_id(ai_runs, "ai_run_id"),
        "task_id": task["task_id"],
        "user_id": task["user_id"],
        "run_type": "TASK_ENRICHMENT",
        "status": "SUCCEEDED",
        "created_at": now,
        "updated_at": now,
    }
    ai_runs.append(ai_run)
    return ai_run


def _build_ai_fields(task):
    priority_weight = {"Critical": 10, "High": 8, "Medium": 5, "Low": 3}.get(task["priority"], 5)
    effort = task.get("estimated_minutes") or 60
    impact = min(10, max(1, priority_weight))
    priority_score = round(
        min(0.99, (priority_weight * 0.58 + impact * 0.32 + min(effort / 60, 4) * 0.1) / 10),
        2,
    )
    difficulty = "Hard" if effort >= 105 or priority_weight >= 9 else "Easy" if effort <= 35 and priority_weight <= 5 else "Medium"
    xp_value = task.get("xp_value")
    if xp_value is None:
        xp_value = max(10, round((effort * 0.75 + impact * 9 + priority_weight * 5) / 10) * 10)
    return {
        "xp_value": xp_value,
        "difficulty": difficulty,
        "impact": impact,
        "priority_score": priority_score,
        "ai_insight": f"{task['priority']} priority {task['task_type']} with {effort} minutes expected effort.",
    }


def _response_task(task, work_date=None):
    response = _with_frontend_aliases(dict(task))
    worked_dates = _task_worked_dates(task)
    requested_date = _normalize_date(work_date, "worked_date") if work_date else _today_key(_now_iso())
    response["worked_dates"] = worked_dates
    response["workedDates"] = worked_dates
    response["working_today"] = requested_date in worked_dates
    response["workingToday"] = response["working_today"]
    return response


def _with_frontend_aliases(task):
    worked_dates = _task_worked_dates(task)
    task["worked_dates"] = _worked_dates_to_storage(worked_dates)
    task["source"] = task["external_source"]
    task["type"] = task["task_type"]
    task["externalId"] = task["external_id"]
    task["projectKey"] = task["project_key"]
    task["dueDate"] = task["due_at"]
    task["startDate"] = task["start_at"]
    task["time"] = task["estimated_minutes"]
    task["actualMinutes"] = task["actual_minutes"]
    task["xp"] = task["xp_value"]
    task["workedDates"] = worked_dates
    task["working_today"] = _has_worked_date(task, _today_key(_now_iso()))
    task["workingToday"] = task["working_today"]
    task["completedAt"] = task["completed_at"]
    if "priority_score" in task:
        task["priorityScore"] = task["priority_score"]
    if "ai_insight" in task:
        task["aiInsight"] = task["ai_insight"]
    return task
