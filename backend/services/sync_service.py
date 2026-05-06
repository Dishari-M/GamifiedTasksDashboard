from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from services.filesystem_store import read_records, with_store_lock, write_records


SYNC_RUNS_FILE = "sync_runs.json"
CALENDAR_EVENTS_FILE = "calendar_events.json"
WORK_ITEMS_FILE = "work_items.json"
WORK_ITEM_EVENTS_FILE = "work_item_events.json"
DAILY_WORK_ITEMS_FILE = "daily_work_items.json"
USERS_FILE = "users.json"
LOCAL_OFFSET = timezone(timedelta(hours=5, minutes=30))


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _today_key():
    return datetime.now(LOCAL_OFFSET).date().isoformat()


def _next_id(records, field):
    ids = [record.get(field, 0) for record in records if isinstance(record.get(field), int)]
    return max(ids, default=0) + 1


def _user_profile(user_id):
    users = read_records(USERS_FILE)
    for user in users:
        if str(user.get("user_id") or user.get("id")) == str(user_id):
            return user
    return {}


def _first_jira_key(user_id):
    tasks = read_records(WORK_ITEMS_FILE)
    for task in tasks:
        if task.get("user_id") != user_id:
            continue
        if task.get("external_source") != "Jira" and task.get("source") != "Jira":
            continue
        key = str(task.get("external_id") or task.get("externalId") or "").strip().upper()
        if key:
            return key
    return ""


def _sync_run_response(run):
    return {
        **run,
        "last_sync_at": run.get("completed_at") or run.get("started_at"),
    }


def latest_sync_run(user_id):
    def action():
        runs = [run for run in read_records(SYNC_RUNS_FILE) if run.get("user_id") == user_id]
        if not runs:
            return {
                "sync_run_id": None,
                "status": "idle",
                "started_at": None,
                "completed_at": None,
                "last_sync_at": None,
                "sources": _idle_sources(),
            }
        return _sync_run_response(sorted(runs, key=lambda run: run.get("started_at") or "", reverse=True)[0])

    return with_store_lock(action)


def list_calendar_events(date=None, user_id=None):
    def action():
        work_date = date or _today_key()
        events = [
            event
            for event in read_records(CALENDAR_EVENTS_FILE)
            if event.get("event_date") == work_date and (not user_id or event.get("user_id") == user_id)
        ]
        active = [event for event in events if not event.get("removed")]
        return sorted(active, key=lambda event: event.get("start_at") or "")

    return with_store_lock(action)


def list_removed_calendar_events(date=None, user_id=None):
    def action():
        work_date = date or _today_key()
        events = [
            event
            for event in read_records(CALENDAR_EVENTS_FILE)
            if event.get("event_date") == work_date
            and (not user_id or event.get("user_id") == user_id)
            and event.get("removed")
        ]
        return sorted(events, key=lambda event: event.get("removed_at") or event.get("start_at") or "", reverse=True)

    return with_store_lock(action)


async def fetch_outlook_calendar_events(codex_config, user_id, date):
    work_date = _normalize_date(date)
    result = await _sync_outlook(codex_config, user_id, work_date)
    if result.get("status") == "FAILED":
        raise HTTPException(
            status_code=502,
            detail={
                "code": "OUTLOOK_CALENDAR_FETCH_FAILED",
                "message": result.get("message") or "Outlook Calendar fetch failed.",
                "error": result.get("error") or "",
            },
        )
    return {
        "date": work_date,
        "items": result.get("events", []),
        "source": result,
    }


def remove_calendar_event(event_id, user_id):
    def action():
        events = read_records(CALENDAR_EVENTS_FILE)
        event_id_text = str(event_id)
        removed = None
        for event in events:
            if str(event.get("event_id")) == event_id_text and event.get("user_id") == user_id:
                removed = event
                event["removed"] = True
                event["removed_at"] = _now_iso()
                event["updated_at"] = event["removed_at"]
                break

        if removed is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "CALENDAR_EVENT_NOT_FOUND", "message": "Calendar event was not found."},
            )

        write_records(CALENDAR_EVENTS_FILE, events)
        return {"removed": True, "event": removed}

    return with_store_lock(action)


def restore_calendar_event(event_id, user_id):
    def action():
        events = read_records(CALENDAR_EVENTS_FILE)
        event_id_text = str(event_id)
        restored = None
        for event in events:
            if str(event.get("event_id")) == event_id_text and event.get("user_id") == user_id:
                restored = event
                event["removed"] = False
                event["restored_at"] = _now_iso()
                event["updated_at"] = event["restored_at"]
                break

        if restored is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "CALENDAR_EVENT_NOT_FOUND", "message": "Calendar event was not found."},
            )

        write_records(CALENDAR_EVENTS_FILE, events)
        return {"restored": True, "event": restored}

    return with_store_lock(action)


def update_calendar_event(event_id, user_id, payload):
    title = str((payload or {}).get("title") or "").strip()
    if not title:
        raise HTTPException(
            status_code=422,
            detail={"code": "CALENDAR_EVENT_TITLE_REQUIRED", "message": "Calendar event title is required."},
        )

    def action():
        events = read_records(CALENDAR_EVENTS_FILE)
        event_id_text = str(event_id)
        updated = None
        for event in events:
            if str(event.get("event_id")) == event_id_text and event.get("user_id") == user_id:
                updated = event
                event["title"] = title
                event["updated_at"] = _now_iso()
                break

        if updated is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "CALENDAR_EVENT_NOT_FOUND", "message": "Calendar event was not found."},
            )

        write_records(CALENDAR_EVENTS_FILE, events)
        return {"updated": True, "event": updated}

    return with_store_lock(action)


async def run_sync(codex_config, user_id, sources=None):
    selected_sources = _selected_sync_sources(sources)
    started_at = _now_iso()
    run = {
        "sync_run_id": None,
        "user_id": user_id,
        "status": "RUNNING",
        "started_at": started_at,
        "completed_at": None,
        "sources": _running_sources(selected_sources),
        "calendar_events": [],
    }

    jobs = {}
    if "Jira" in selected_sources:
        jobs["Jira"] = _sync_jira(codex_config, user_id)
    if "Outlook Calendar" in selected_sources:
        jobs["Outlook Calendar"] = _sync_outlook(codex_config, user_id)

    results = await asyncio.gather(*jobs.values()) if jobs else []
    result_by_source = dict(zip(jobs.keys(), results))
    completed_at = _now_iso()

    jira_result = result_by_source.get("Jira") or _source_status("Jira", "IDLE", "Not selected.")
    outlook_result = result_by_source.get("Outlook Calendar") or _source_status("Outlook Calendar", "IDLE", "Not selected.")
    run["sources"] = [jira_result, outlook_result]
    run["calendar_events"] = outlook_result.get("events", [])
    run["status"] = "SUCCEEDED" if all(item["status"] in {"SUCCEEDED", "SKIPPED", "IDLE"} for item in run["sources"]) else "PARTIAL"
    run["completed_at"] = completed_at

    def action():
        runs = read_records(SYNC_RUNS_FILE)
        run["sync_run_id"] = _next_id(runs, "sync_run_id")
        runs.append(run)
        write_records(SYNC_RUNS_FILE, runs)
        return _sync_run_response(run)

    return with_store_lock(action)


async def _sync_jira(codex_config, user_id):
    email = ""
    try:
        profile = with_store_lock(lambda: _user_profile(user_id))
        email = str(profile.get("email") or "").strip()
        if not email:
            return _source_status("Jira", "FAILED", "Jira sync requires the logged-in user's email address.")
        output = await codex_config.run_codex_async(_jira_sync_prompt(codex_config, email))
        if codex_config.looks_like_mcp_auth_cancelled(output):
            return _source_status("Jira", "FAILED", "Jira MCP authentication is required.", "Complete Jira SSO, then sync again.")
        payload = codex_config.extract_json_object(output)
        issues = _normalize_jira_issues(payload, codex_config, email)
        if not issues:
            return {
                **_source_status("Jira", "SUCCEEDED", "No open Jira issues assigned to this user."),
                "tasks": [],
                "created": 0,
                "updated": 0,
            }
        sync_result = _upsert_jira_work_items(user_id, issues)
        count = len(sync_result["tasks"])
        created = sync_result["created"]
        updated = sync_result["updated"]
        return {
            **_source_status("Jira", "SUCCEEDED", f"Synced {count} open Jira issue{'s' if count != 1 else ''}: {created} added, {updated} updated."),
            **sync_result,
        }
    except Exception as exc:
        detail = getattr(exc, "detail", None)
        if isinstance(detail, dict):
            message = detail.get("message") or str(detail)
        else:
            message = str(detail or exc)
        return _source_status("Jira", "FAILED", f"Jira sync failed{f' for {email}' if email else ''}.", message)


def _jira_sync_prompt(codex_config, email):
    return f"""
You are a DevQuest Jira bulk sync worker.

Use Jira MCP server: {codex_config.JIRA_MCP_SERVER}.
Find all the open Jiras assigned to this email address only:
{email}

Include assigned open Jiras across all projects and prefixes, such as HRA, HEPRT, HLM, and any other project, as long as they are assigned to {email}.

Return only one valid JSON object, with no markdown, in this exact shape:
{{
  "issues": [
    {{
      "jira_key": "ABC-123",
      "title": "Jira summary",
      "description": "Jira description or concise summary",
      "priority": "Critical|High|Medium|Low",
      "status": "Jira status",
      "type": "Task|Bug|Epic|Review|Meeting",
      "labels": ["label"],
      "project_key": "ABC",
      "due_at": "YYYY-MM-DD or empty",
      "assignee_email": "{email}"
    }}
  ]
}}

Open Jira definition:
- A Jira is open when its status is not Closed and not Done.
- Statuses such as "Development to QA" and "Require Documentation" are still open and must be included.
- Do not exclude a Jira just because it is beyond initial development; exclude it only when it is Closed/Done-style or has a resolution set.

Rules:
1. Fetch real Jira data through the MCP server.
2. Include only issues assigned to {email}.
3. Include only open issues. Exclude issues whose status is Closed or Done, whose status category is Done, or whose resolution is set. Exclude Done, Closed, Resolved, Cancelled, Canceled, Duplicate, and Won't Do issues.
4. Include all Jira project types/prefixes. Do not filter to a known prefix list.
5. Fetch enough fields for each issue to populate a task: key, summary/title, description, priority, status, issue type, labels, project key, and due date when available.
6. If no issue is available, return {{"issues": []}}.
"""


def _normalize_jira_issues(payload, codex_config, assignee_email=""):
    raw_issues = payload.get("issues") or payload.get("jiras") or payload.get("tasks") or []
    if not raw_issues and (payload.get("jira_key") or payload.get("key")):
        raw_issues = [payload]
    if not isinstance(raw_issues, list):
        return []

    normalized = []
    seen = set()
    for raw_issue in raw_issues:
        if not isinstance(raw_issue, dict):
            continue
        returned_assignee_email = _jira_assignee_email(raw_issue)
        if returned_assignee_email and assignee_email and returned_assignee_email.lower() != assignee_email.lower():
            continue
        jira_key = str(raw_issue.get("jira_key") or raw_issue.get("key") or raw_issue.get("external_id") or "").strip().upper()
        status = _jira_field_text(raw_issue.get("status"))
        status_category = _jira_status_category(raw_issue.get("status"))
        resolution = _jira_field_text(raw_issue.get("resolution"))
        if not jira_key or jira_key in seen or _is_closed_jira_status(status, status_category, resolution):
            continue
        title = str(raw_issue.get("title") or raw_issue.get("summary") or jira_key).strip()
        description = str(raw_issue.get("description") or raw_issue.get("body") or title).strip()
        labels = raw_issue.get("labels") or []
        if not isinstance(labels, list):
            labels = str(labels).split(",")
        project_key = str(_jira_project_key(raw_issue.get("project_key") or raw_issue.get("project")) or jira_key.split("-", 1)[0]).strip().upper()
        issue_type = _jira_field_text(raw_issue.get("type") or raw_issue.get("issue_type") or raw_issue.get("issuetype"))
        normalized.append(
            {
                "jira_key": jira_key,
                "title": title or jira_key,
                "description": description,
                "priority": codex_config.normalize_jira_priority(_jira_field_text(raw_issue.get("priority"))),
                "status": status,
                "task_type": codex_config.normalize_jira_task_type(issue_type),
                "labels": [str(label).strip() for label in labels if str(label).strip()],
                "project_key": project_key or None,
                "due_at": _date_or_none(raw_issue.get("due_at") or raw_issue.get("due") or raw_issue.get("duedate")),
            }
        )
        seen.add(jira_key)
    return normalized


def _jira_assignee_email(issue):
    explicit = str(issue.get("assignee_email") or issue.get("assigneeEmail") or "").strip()
    if explicit:
        return explicit
    assignee = issue.get("assignee") or {}
    if isinstance(assignee, dict):
        return str(assignee.get("email") or assignee.get("emailAddress") or assignee.get("mail") or "").strip()
    return ""


def _jira_field_text(value):
    if isinstance(value, dict):
        return str(
            value.get("name")
            or value.get("key")
            or value.get("display_name")
            or value.get("displayName")
            or value.get("email")
            or ""
        ).strip()
    return str(value or "").strip()


def _jira_project_key(value):
    if isinstance(value, dict):
        return str(value.get("key") or value.get("name") or "").strip()
    return str(value or "").strip()


def _jira_status_category(status):
    if not isinstance(status, dict):
        return ""
    category = status.get("category") or status.get("statusCategory") or {}
    if isinstance(category, dict):
        return _jira_field_text(category)
    return _jira_field_text(category)


def _is_closed_jira_status(status, status_category="", resolution=""):
    if resolution:
        return True
    if str(status_category or "").strip().lower() == "done":
        return True
    normalized = str(status or "").strip().lower()
    if normalized in {"development to qa", "require documentation", "requires documentation"}:
        return False
    return any(
        closed in normalized
        for closed in ("done", "closed", "resolved", "cancelled", "canceled", "duplicate", "won't do", "wont do", "rejected")
    )


def _date_or_none(value):
    text = str(value or "").strip()
    if not text:
        return None
    return text[:10]


def _upsert_jira_work_items(user_id, issues):
    def action():
        tasks = read_records(WORK_ITEMS_FILE)
        events = read_records(WORK_ITEM_EVENTS_FILE)
        daily_items = read_records(DAILY_WORK_ITEMS_FILE)
        now = _now_iso()
        today = _today_key()
        created = 0
        updated = 0
        synced_tasks = []

        task_by_jira_key = {
            str(task.get("external_id") or task.get("externalId") or "").strip().upper(): task
            for task in tasks
            if task.get("user_id") == user_id and task.get("external_source") == "Jira"
        }

        next_task_id = _next_id(tasks, "task_id")
        next_event_id = _next_id(events, "event_id")
        for issue in issues:
            jira_key = issue["jira_key"]
            task = task_by_jira_key.get(jira_key)
            if task is None:
                task = _new_jira_task(next_task_id, user_id, issue, now, today)
                next_task_id += 1
                tasks.append(task)
                task_by_jira_key[jira_key] = task
                events.append(_work_item_event(next_event_id, task, "TASK_CREATED", now, task))
                next_event_id += 1
                created += 1
            else:
                _update_jira_task(task, issue, now, today)
                events.append(
                    _work_item_event(
                        next_event_id,
                        task,
                        "JIRA_SYNC_UPDATED",
                        now,
                        {"jira_key": jira_key, "status": issue.get("status"), "synced_at": now},
                    )
                )
                next_event_id += 1
                updated += 1

            _upsert_sync_daily_work_item(daily_items, task, now, today)
            synced_tasks.append(_task_response(task))

        write_records(WORK_ITEMS_FILE, tasks)
        write_records(WORK_ITEM_EVENTS_FILE, events)
        write_records(DAILY_WORK_ITEMS_FILE, daily_items)
        return {"tasks": synced_tasks, "created": created, "updated": updated}

    return with_store_lock(action)


def _new_jira_task(task_id, user_id, issue, now, today):
    task = {
        "task_id": task_id,
        "id": str(task_id),
        "user_id": user_id,
        "external_source": "Jira",
        "external_id": issue["jira_key"],
        "title": issue["title"],
        "description": issue["description"],
        "task_type": issue["task_type"],
        "priority": issue["priority"],
        "status": "In Progress",
        "project_key": issue.get("project_key"),
        "due_at": issue.get("due_at"),
        "start_at": None,
        "estimated_minutes": 60,
        "actual_minutes": 0,
        "xp_value": 60,
        "notes": f"Jira status at sync: {issue.get('status') or 'Open'}",
        "labels": issue.get("labels") or [],
        "worked_dates": today,
        "working_today": True,
        "run_ai_enrichment": False,
        "row_version": 1,
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
        "difficulty": "Medium",
        "impact": _impact_for_priority(issue["priority"]),
        "priority_score": _priority_score(issue["priority"]),
        "ai_insight": f"{issue['priority']} priority {issue['task_type']} synced from Jira.",
    }
    return _with_task_aliases(task)


def _update_jira_task(task, issue, now, today):
    task.update(
        {
            "title": issue["title"],
            "description": issue["description"],
            "task_type": issue["task_type"],
            "priority": issue["priority"],
            "status": "In Progress",
            "project_key": issue.get("project_key"),
            "due_at": issue.get("due_at"),
            "completed_at": None,
            "labels": issue.get("labels") or [],
            "working_today": True,
            "updated_at": now,
            "row_version": int(task.get("row_version") or 1) + 1,
            "impact": _impact_for_priority(issue["priority"]),
            "priority_score": _priority_score(issue["priority"]),
            "ai_insight": f"{issue['priority']} priority {issue['task_type']} synced from Jira.",
        }
    )
    worked_dates = _worked_dates(task)
    if today not in worked_dates:
        worked_dates.append(today)
    task["worked_dates"] = ",".join(sorted(set(worked_dates)))
    _with_task_aliases(task)


def _upsert_sync_daily_work_item(daily_items, task, now, today):
    for item in daily_items:
        if item.get("user_id") == task["user_id"] and item.get("task_id") == task["task_id"] and item.get("work_date") == today:
            item["is_working_today"] = True
            item["updated_at"] = now
            return item
    item = {
        "daily_work_item_id": _next_id(daily_items, "daily_work_item_id"),
        "task_id": task["task_id"],
        "user_id": task["user_id"],
        "work_date": today,
        "is_working_today": True,
        "created_at": now,
        "updated_at": now,
    }
    daily_items.append(item)
    return item


def _work_item_event(event_id, task, event_type, now, payload):
    return {
        "event_id": event_id,
        "task_id": task["task_id"],
        "user_id": task["user_id"],
        "event_type": event_type,
        "created_at": now,
        "payload": payload,
    }


def _worked_dates(task):
    value = task.get("worked_dates") or task.get("workedDates") or ""
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _impact_for_priority(priority):
    return {"Critical": 10, "High": 8, "Medium": 5, "Low": 3}.get(priority, 5)


def _priority_score(priority):
    return round(min(0.99, (_impact_for_priority(priority) * 0.9 + 0.1) / 10), 2)


def _task_response(task):
    return _with_task_aliases(dict(task))


def _with_task_aliases(task):
    worked_dates = sorted(set(_worked_dates(task)))
    task["worked_dates"] = ",".join(worked_dates)
    task["source"] = task["external_source"]
    task["type"] = task["task_type"]
    task["externalId"] = task["external_id"]
    task["projectKey"] = task.get("project_key")
    task["dueDate"] = task.get("due_at")
    task["startDate"] = task.get("start_at")
    task["time"] = task.get("estimated_minutes")
    task["actualMinutes"] = task.get("actual_minutes")
    task["xp"] = task.get("xp_value")
    task["workedDates"] = worked_dates
    task["working_today"] = bool(task.get("working_today"))
    task["workingToday"] = bool(task.get("working_today"))
    task["completedAt"] = task.get("completed_at")
    if "priority_score" in task:
        task["priorityScore"] = task["priority_score"]
    if "ai_insight" in task:
        task["aiInsight"] = task["ai_insight"]
    task["jiraTshirtSize"] = task.get("jira_tshirt_size")
    task["jiraTshirtSizing"] = task.get("jira_tshirt_sizing")
    return task


async def _sync_outlook(codex_config, user_id, work_date=None):
    try:
        profile = with_store_lock(lambda: _user_profile(user_id))
        email = str(profile.get("email") or "").strip()
        target_date = _normalize_date(work_date or _today_key())
        start = f"{target_date}T00:00:00+05:30"
        end = f"{target_date}T23:59:59+05:30"
        prompt = _outlook_prompt(email, target_date, start, end)
        output = await codex_config.run_codex_async(prompt)
        payload = codex_config.extract_json_object(output)
        events = _normalize_outlook_events(payload.get("events") or [], user_id, target_date)
        _replace_calendar_events(user_id, target_date, events)
        count = len(events)
        return {
            **_source_status("Outlook Calendar", "SUCCEEDED", f"Fetched {count} event{'s' if count != 1 else ''} for {target_date}."),
            "events": events,
        }
    except Exception as exc:
        return {
            **_source_status("Outlook Calendar", "FAILED", "Outlook Calendar sync failed.", str(exc)),
            "events": [],
        }


def _outlook_prompt(email, today, start, end):
    return f"""
You are syncing DevQuest with Outlook Calendar.

Use the enabled Outlook Calendar plugin from the Codex config, especially list_events.
Fetch the signed-in user's default Outlook Calendar events for this exact window:
start_datetime: {start}
end_datetime: {end}

The DevQuest logged-in user's email is: {email or "unknown"}.
If mailbox settings expose the signed-in mailbox, use it only to verify context. Do not modify any calendar events.

Return only one valid JSON object, with no markdown, in this exact shape:
{{
  "events": [
    {{
      "external_id": "Outlook event id if available",
      "title": "event subject",
      "start_at": "ISO start timestamp",
      "end_at": "ISO end timestamp",
      "duration_minutes": 30,
      "is_meeting": true,
      "is_focus_block": false,
      "location": "optional location",
      "status": "Busy/Tentative/Free if available"
    }}
  ]
}}

Rules:
1. Include only timed meetings/events that occur on {today}.
2. Preserve Outlook subjects as titles.
3. Use ISO timestamps that JavaScript can parse.
4. Compute duration_minutes from start and end.
5. Mark is_focus_block true only for focus-time or focus-block events.
6. Exclude all-day events, multi-day events, holidays, OOO/out-of-office entries, declined events, and availability-only blocks.
7. If there are no events, return "events": [].
"""


def _normalize_outlook_events(raw_events, user_id, work_date):
    normalized = []
    now = _now_iso()
    for index, raw_event in enumerate(raw_events):
        if not isinstance(raw_event, dict):
            continue
        title = str(raw_event.get("title") or raw_event.get("subject") or "Outlook event").strip()
        start_at = _iso_text(raw_event.get("start_at") or raw_event.get("start"))
        end_at = _iso_text(raw_event.get("end_at") or raw_event.get("end"))
        duration = _duration_minutes(start_at, end_at, raw_event.get("duration_minutes"))
        if _should_hide_outlook_event(title, start_at, end_at, duration, raw_event):
            continue
        lower_title = title.lower()
        normalized.append(
            {
                "event_id": index + 1,
                "user_id": user_id,
                "event_date": work_date,
                "external_source": "Outlook Calendar",
                "external_id": str(raw_event.get("external_id") or raw_event.get("id") or f"outlook-{work_date}-{index + 1}"),
                "title": title,
                "start_at": start_at,
                "end_at": end_at,
                "duration_minutes": duration,
                "is_meeting": not ("focus" in lower_title),
                "is_focus_block": bool(raw_event.get("is_focus_block")) or "focus" in lower_title,
                "location": raw_event.get("location") or "",
                "status": raw_event.get("status") or "",
                "created_at": now,
                "updated_at": now,
            }
        )
    return sorted(normalized, key=lambda event: event.get("start_at") or "")


def _should_hide_outlook_event(title, start_at, end_at, duration, raw_event):
    lower_title = str(title or "").lower()
    location = str(raw_event.get("location") or "").lower()
    status = str(raw_event.get("status") or raw_event.get("show_as") or raw_event.get("showAs") or "").lower()
    response = str(raw_event.get("response") or raw_event.get("response_status") or raw_event.get("responseStatus") or "").lower()
    is_all_day = bool(raw_event.get("is_all_day") or raw_event.get("isAllDay"))
    if duration >= 8 * 60:
        is_all_day = True
    if "ooo" in lower_title or "out of office" in lower_title or "out of office" in location or "oof" in status:
        return True
    if "declined" in response or status == "free":
        return True
    return is_all_day


def _replace_calendar_events(user_id, work_date, events):
    def action():
        existing = [
            event
            for event in read_records(CALENDAR_EVENTS_FILE)
            if not (
                event.get("user_id") == user_id
                and event.get("event_date") == work_date
                and not event.get("removed")
            )
        ]
        next_id = _next_id(existing, "event_id")
        for event in events:
            event["event_id"] = next_id
            next_id += 1
        write_records(CALENDAR_EVENTS_FILE, existing + events)

    return with_store_lock(action)


def _normalize_date(value):
    text = str(value or "").strip()
    if not text:
        return _today_key()
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "date must use YYYY-MM-DD format."},
        ) from exc
    return text


def _duration_minutes(start_at, end_at, fallback=None):
    try:
        if fallback not in (None, ""):
            return max(0, int(float(fallback)))
    except (TypeError, ValueError):
        pass
    try:
        start_dt = datetime.fromisoformat(str(start_at).replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(str(end_at).replace("Z", "+00:00"))
        return max(0, round((end_dt - start_dt).total_seconds() / 60))
    except Exception:
        return 0


def _iso_text(value):
    if isinstance(value, dict):
        date_time = value.get("dateTime") or value.get("date_time")
        timezone_name = value.get("timeZone") or value.get("time_zone")
        if date_time and timezone_name:
            return str(date_time)
    return str(value or "")


def _source_status(source, status, message, error=""):
    return {
        "source": source,
        "status": status,
        "message": message,
        "error": error,
    }


def _selected_sync_sources(sources):
    allowed = {"Jira", "Outlook Calendar"}
    if not sources:
        return allowed
    selected = {str(source).strip() for source in sources if str(source).strip() in allowed}
    return selected or allowed


def _running_sources(selected_sources):
    return [
        _source_status(
            "Jira",
            "RUNNING" if "Jira" in selected_sources else "IDLE",
            "Syncing Jira issues..." if "Jira" in selected_sources else "Not selected.",
        ),
        _source_status(
            "Outlook Calendar",
            "RUNNING" if "Outlook Calendar" in selected_sources else "IDLE",
            "Fetching today's Outlook meetings." if "Outlook Calendar" in selected_sources else "Not selected.",
        ),
    ]


def _idle_sources():
    return [
        _source_status("Jira", "IDLE", "Ready to sync."),
        _source_status("Outlook Calendar", "IDLE", "Ready to sync."),
    ]
