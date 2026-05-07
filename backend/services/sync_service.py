from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import oracledb
from fastapi import HTTPException

from db import get_connection
from repositories import task_repository
from services.api_cache import invalidate_user_cache
from services.filesystem_store import read_records, with_store_lock, write_records
from services.user_context import parse_oracle_user_id


SYNC_RUNS_FILE = "sync_runs.json"
CALENDAR_EVENTS_FILE = "calendar_events.json"
LOCAL_OFFSET = timezone(timedelta(hours=5, minutes=30))
OUTLOOK_EVENT_SOURCE = "Outlook"
OUTLOOK_SYNC_SOURCES = ("Outlook", "Outlook Calendar")
TASK_RELATED_CACHE_NAMESPACES = ("task_list", "dashboard_today", "insights_today")
CALENDAR_RELATED_CACHE_NAMESPACES = ("dashboard_today", "capacity", "insights_today")


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _today_key():
    return datetime.now(LOCAL_OFFSET).date().isoformat()


def _next_id(records, field):
    ids = [record.get(field, 0) for record in records if isinstance(record.get(field), int)]
    return max(ids, default=0) + 1


def _user_profile(user_id):
    oracle_user_id = parse_oracle_user_id(user_id)
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT USER_ID, DISPLAY_NAME, EMAIL, ROLE_NAME, TIMEZONE
            FROM APP_USERS
            WHERE USER_ID = :user_id
            """,
            {"user_id": oracle_user_id},
        )
        row = cur.fetchone()
        if not row:
            return {}
        return {
            "user_id": row[0],
            "id": f"user-{row[0]}",
            "display_name": row[1],
            "email": row[2],
            "role_name": row[3],
            "timezone": row[4],
        }
    finally:
        if conn:
            conn.close()


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
    if user_id is not None:
        return _list_oracle_calendar_events(user_id, date or _today_key())

    def action():
        work_date = date or _today_key()
        events = [event for event in read_records(CALENDAR_EVENTS_FILE) if event.get("event_date") == work_date]
        active = [event for event in events if not event.get("removed")]
        return sorted(active, key=lambda event: event.get("start_at") or "")

    return with_store_lock(action)


def list_removed_calendar_events(date=None, user_id=None):
    if user_id is not None:
        return []

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
    oracle_user_id = parse_oracle_user_id(user_id)
    event = _fetch_oracle_calendar_event(oracle_user_id, event_id)
    if event:
        _delete_oracle_calendar_event(oracle_user_id, event_id)
        return {"removed": True, "event": event}

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
    if _fetch_oracle_calendar_event(parse_oracle_user_id(user_id), event_id):
        return {"restored": True, "event": _fetch_oracle_calendar_event(parse_oracle_user_id(user_id), event_id)}

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

    oracle_user_id = parse_oracle_user_id(user_id)
    event = _update_oracle_calendar_event(oracle_user_id, event_id, title)
    if event:
        return {"updated": True, "event": event}

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
    project_keys = "HRA, HEPRT, HLM"
    return f"""
You are a DevQuest Jira bulk sync worker.

Use Jira MCP server: {codex_config.JIRA_MCP_SERVER}.
Find all Jira issues assigned to the logged-in DevQuest user in these projects:
{project_keys}

Search with this exact JQL:
project IN ({project_keys}) AND assignee = "{email}"

Then classify issues by status name only, not statusCategory and not resolution:
- Closed if the status name contains: closed, done, complete
- Open if the status name contains: work in progress, in-progress, to-do, to do, QA to dev, dev to QA, waiting, require development, awaiting, engineering, code hardware bug, open
- If neither rule matches, list it separately as "uncertain" in the response metadata, but do not include it in "issues".

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
      "created": "YYYY-MM-DD or empty",
      "updated": "YYYY-MM-DD or empty",
      "assignee_email": "{email}"
    }}
  ],
  "uncertain": [
    {{
      "jira_key": "ABC-456",
      "status": "Jira status",
      "priority": "Critical|High|Medium|Low",
      "title": "Jira summary",
      "created": "YYYY-MM-DD or empty",
      "updated": "YYYY-MM-DD or empty"
    }}
  ]
}}

Rules:
1. Fetch real Jira data through the MCP server.
2. Include only issues assigned to {email}.
3. Include only open issues in "issues" using the status-name rules above.
4. Do not use statusCategory or resolution to classify open vs closed.
5. Fetch enough fields for each issue to populate a task: key, summary/title, description, priority, status, issue type, labels, project key, due date, created, and updated when available.
6. If no open issue is available, return {{"issues": [], "uncertain": []}}.
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
        if not jira_key or jira_key in seen or not _is_open_jira_status_name(status):
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


def _is_open_jira_status_name(status):
    normalized = str(status or "").strip().lower()
    if any(closed in normalized for closed in ("closed", "done", "complete")):
        return False
    return any(
        open_status in normalized
        for open_status in (
            "work in progress",
            "in-progress",
            "to-do",
            "to do",
            "qa to dev",
            "dev to qa",
            "waiting",
            "require development",
            "awaiting",
            "engineering",
            "code hardware bug",
            "open",
        )
    )


def _date_or_none(value):
    text = str(value or "").strip()
    if not text:
        return None
    return text[:10]


def _upsert_jira_work_items(user_id, issues):
    oracle_user_id = parse_oracle_user_id(user_id)
    today = _today_key()
    created = 0
    updated = 0
    synced_tasks = []
    conn = None

    try:
        conn = get_connection()
        cur = conn.cursor()
        for issue in issues:
            jira_key = issue["jira_key"]
            existing = task_repository.fetch_task_by_external_identity_for_update(
                cur,
                oracle_user_id,
                "Jira",
                jira_key,
            )
            if existing is None:
                task = _jira_task_payload(issue, today)
                ai = _jira_ai_payload(issue)
                task_id = task_repository.insert_task(cur, oracle_user_id, task, ai)
                task_repository.insert_work_date(cur, oracle_user_id, task_id, today, task["estimated_minutes"])
                task_repository.insert_task_event(
                    cur,
                    oracle_user_id,
                    task_id,
                    "TASK_CREATED",
                    None,
                    {"source": "Jira", "jira_key": jira_key, "synced_at": _now_iso()},
                )
                created += 1
            else:
                task_id = existing["task_id"]
                fields = _jira_update_fields(issue)
                task_repository.update_task_fields(cur, oracle_user_id, task_id, fields)
                task_repository.insert_work_date(cur, oracle_user_id, task_id, today, 60)
                task_repository.insert_task_event(
                    cur,
                    oracle_user_id,
                    task_id,
                    "JIRA_SYNC_UPDATED",
                    {"row_version": existing["row_version"]},
                    {"jira_key": jira_key, "status": issue.get("status"), "synced_at": _now_iso()},
                )
                updated += 1

            synced_tasks.append(task_repository.fetch_task(cur, oracle_user_id, task_id, today))

        conn.commit()
        invalidate_user_cache(oracle_user_id, TASK_RELATED_CACHE_NAMESPACES)
        return {"tasks": synced_tasks, "created": created, "updated": updated}
    except oracledb.DatabaseError as exc:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=503,
            detail={"code": "JIRA_SYNC_STORAGE_UNAVAILABLE", "message": "Jira sync storage is unavailable."},
        ) from exc
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def _jira_task_payload(issue, today):
    return {
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
        "worked_dates": [today],
        "working_today": True,
        "run_ai_enrichment": False,
    }


def _jira_ai_payload(issue):
    return {
        "difficulty": "Medium",
        "impact_score": _impact_for_priority(issue["priority"]),
        "priority_score": _priority_score(issue["priority"]),
        "effort_minutes": 60,
        "category": issue["task_type"],
        "insight": f"{issue['priority']} priority {issue['task_type']} synced from Jira.",
        "model_id": "jira-sync",
        "xp_value": 60,
    }


def _jira_update_fields(issue):
    return [
        ("TITLE", "title", issue["title"]),
        ("DESCRIPTION", "description", issue["description"]),
        ("TASK_TYPE", "task_type", issue["task_type"]),
        ("PRIORITY", "priority", issue["priority"]),
        ("STATUS", "status", "In Progress"),
        ("PROJECT_KEY", "project_key", issue.get("project_key")),
        ("DUE_DATE", "due_at", issue.get("due_at")),
        ("COMPLETED_AT", "completed_at", None),
        ("ESTIMATED_MINUTES", "estimated_minutes", 60),
        ("XP_VALUE", "xp_value", 60),
        ("NOTES", "notes", f"Jira status at sync: {issue.get('status') or 'Open'}"),
        ("LABELS_JSON", "labels_json", json.dumps(issue.get("labels") or [], separators=(",", ":"))),
        ("AI_DIFFICULTY", "ai_difficulty", "Medium"),
        ("AI_IMPACT_SCORE", "ai_impact_score", _impact_for_priority(issue["priority"])),
        ("AI_PRIORITY_SCORE", "ai_priority_score", _priority_score(issue["priority"])),
        ("AI_EFFORT_MINUTES", "ai_effort_minutes", 60),
        ("AI_CATEGORY", "ai_category", issue["task_type"]),
        ("AI_INSIGHT", "ai_insight", f"{issue['priority']} priority {issue['task_type']} synced from Jira."),
        ("AI_MODEL_VERSION", "ai_model_version", "jira-sync"),
        ("AI_ENRICHED_AT", "ai_enriched_at", datetime.now(timezone.utc)),
    ]


def _impact_for_priority(priority):
    return {"Critical": 10, "High": 8, "Medium": 5, "Low": 3}.get(priority, 5)


def _priority_score(priority):
    return round(min(0.99, (_impact_for_priority(priority) * 0.9 + 0.1) / 10), 2)


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
            **_source_status("Outlook Calendar", "FAILED", "Outlook Calendar sync failed.", _exception_message(exc)),
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
                "external_source": OUTLOOK_EVENT_SOURCE,
                "external_id": _outlook_external_id(raw_event, work_date, start_at, title, index),
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
    if not start_at or not end_at or duration <= 0:
        return True
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


def _outlook_external_id(raw_event, work_date, start_at, title, index):
    external_id = str(
        raw_event.get("external_id")
        or raw_event.get("externalId")
        or raw_event.get("id")
        or raw_event.get("iCalUId")
        or raw_event.get("ical_uid")
        or ""
    ).strip()
    if external_id:
        return external_id[:200]
    stable = f"outlook-{work_date}-{start_at or index}-{title}"
    return stable[:200]


def _replace_calendar_events(user_id, work_date, events):
    oracle_user_id = parse_oracle_user_id(user_id)
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        existing_by_external_id = _oracle_outlook_events_by_external_id(cur, oracle_user_id)
        existing_for_day = _oracle_outlook_events_by_external_id(cur, oracle_user_id, work_date)
        seen_external_ids = set()
        for event in events:
            event["external_source"] = OUTLOOK_EVENT_SOURCE
            event["user_id"] = oracle_user_id
            external_id = str(event.get("external_id") or "").strip()
            if not external_id:
                continue
            seen_external_ids.add(external_id)
            existing = existing_by_external_id.get(external_id)
            if existing:
                event["event_id"] = existing["event_id"]
                _update_oracle_outlook_event(cur, oracle_user_id, existing["event_id"], event)
            else:
                event["event_id"] = _insert_oracle_outlook_event(cur, oracle_user_id, event)
        stale_event_ids = [
            event["event_id"]
            for external_id, event in existing_for_day.items()
            if external_id not in seen_external_ids
        ]
        _delete_stale_oracle_outlook_events(cur, oracle_user_id, stale_event_ids)
        conn.commit()
        invalidate_user_cache(oracle_user_id, CALENDAR_RELATED_CACHE_NAMESPACES)
    except oracledb.DatabaseError as exc:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=503,
            detail={
                "code": "CALENDAR_STORAGE_UNAVAILABLE",
                "message": "Calendar storage is unavailable.",
                "error": _oracle_error_message(exc),
            },
        ) from exc
    finally:
        if conn:
            conn.close()

    return events


def _oracle_outlook_events_by_external_id(cur, user_id, work_date=None):
    source_names = _outlook_source_binds()
    day_filter = ""
    binds = {"user_id": user_id, **source_names["binds"]}
    if work_date:
        day_filter = "AND TRUNC(CAST(START_AT AS TIMESTAMP)) = TO_DATE(:work_date, 'YYYY-MM-DD')"
        binds["work_date"] = work_date
    cur.execute(
        f"""
        SELECT EVENT_ID, EXTERNAL_ID
        FROM CALENDAR_EVENTS
        WHERE USER_ID = :user_id
          AND EXTERNAL_SOURCE IN ({source_names["placeholders"]})
          {day_filter}
        """,
        binds,
    )
    return {
        str(row[1] or "").strip(): {"event_id": row[0], "external_id": row[1]}
        for row in cur.fetchall()
        if str(row[1] or "").strip()
    }


def _insert_oracle_outlook_event(cur, user_id, event):
    event_id = cur.var(int)
    cur.execute(
        """
        INSERT INTO CALENDAR_EVENTS (
            EVENT_ID,
            USER_ID,
            EXTERNAL_SOURCE,
            EXTERNAL_ID,
            TITLE,
            DESCRIPTION,
            START_AT,
            END_AT,
            DURATION_MINUTES,
            IS_MEETING,
            IS_FOCUS_BLOCK,
            ATTENDEE_COUNT,
            CREATED_AT,
            UPDATED_AT,
            ROW_VERSION
        )
        VALUES (
            CALENDAR_EVENTS_SEQ.NEXTVAL,
            :user_id,
            :external_source,
            :external_id,
            :title,
            :description,
            :start_at,
            :end_at,
            :duration_minutes,
            :is_meeting,
            :is_focus_block,
            :attendee_count,
            SYSTIMESTAMP,
            SYSTIMESTAMP,
            1
        )
        RETURNING EVENT_ID INTO :event_id
        """,
        _oracle_calendar_binds(user_id, event, event_id),
    )
    return int(event_id.getvalue()[0])


def _update_oracle_outlook_event(cur, user_id, event_id, event):
    binds = _oracle_calendar_binds(user_id, event)
    binds["event_id"] = event_id
    cur.execute(
        """
        UPDATE CALENDAR_EVENTS
        SET EXTERNAL_SOURCE = :external_source,
            EXTERNAL_ID = :external_id,
            TITLE = :title,
            DESCRIPTION = :description,
            START_AT = :start_at,
            END_AT = :end_at,
            DURATION_MINUTES = :duration_minutes,
            IS_MEETING = :is_meeting,
            IS_FOCUS_BLOCK = :is_focus_block,
            ATTENDEE_COUNT = :attendee_count,
            UPDATED_AT = SYSTIMESTAMP,
            ROW_VERSION = ROW_VERSION + 1
        WHERE USER_ID = :user_id
          AND EVENT_ID = :event_id
        """,
        binds,
    )


def _delete_stale_oracle_outlook_events(cur, user_id, event_ids):
    if not event_ids:
        return
    binds = {"user_id": user_id}
    placeholders = []
    for index, event_id in enumerate(event_ids):
        bind = f"event_id_{index}"
        binds[bind] = event_id
        placeholders.append(f":{bind}")
    cur.execute(
        f"""
        DELETE FROM CALENDAR_EVENTS
        WHERE USER_ID = :user_id
          AND EVENT_ID IN ({", ".join(placeholders)})
        """,
        binds,
    )


def _oracle_calendar_binds(user_id, event, event_id=None):
    binds = {
        "user_id": user_id,
        "external_source": _max_text(event.get("external_source") or OUTLOOK_EVENT_SOURCE, 40),
        "external_id": _max_text(event.get("external_id"), 200),
        "title": _max_text(event.get("title") or "Outlook event", 300),
        "description": event.get("description") or "",
        "start_at": _datetime_or_none(event.get("start_at")),
        "end_at": _datetime_or_none(event.get("end_at")),
        "duration_minutes": event.get("duration_minutes") or 0,
        "is_meeting": 1 if event.get("is_meeting") else 0,
        "is_focus_block": 1 if event.get("is_focus_block") else 0,
        "attendee_count": event.get("attendee_count") or 0,
    }
    if event_id is not None:
        binds["event_id"] = event_id
    return binds


def _outlook_source_binds():
    binds = {}
    placeholders = []
    for index, source in enumerate(OUTLOOK_SYNC_SOURCES):
        bind = f"source_{index}"
        binds[bind] = source
        placeholders.append(f":{bind}")
    return {"binds": binds, "placeholders": ", ".join(placeholders)}


def _list_oracle_calendar_events(user_id, work_date):
    oracle_user_id = parse_oracle_user_id(user_id)
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                EVENT_ID,
                USER_ID,
                EXTERNAL_SOURCE,
                EXTERNAL_ID,
                TITLE,
                DESCRIPTION,
                TO_CHAR(START_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM') AS START_AT,
                TO_CHAR(END_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM') AS END_AT,
                DURATION_MINUTES,
                IS_MEETING,
                IS_FOCUS_BLOCK,
                ATTENDEE_COUNT,
                TO_CHAR(CREATED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM') AS CREATED_AT,
                TO_CHAR(UPDATED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM') AS UPDATED_AT,
                ROW_VERSION
            FROM CALENDAR_EVENTS
            WHERE USER_ID = :user_id
              AND TRUNC(CAST(START_AT AS TIMESTAMP)) = TO_DATE(:work_date, 'YYYY-MM-DD')
            ORDER BY START_AT
            """,
            {"user_id": oracle_user_id, "work_date": work_date},
        )
        return [_calendar_event_row(row) for row in cur.fetchall()]
    except oracledb.DatabaseError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "CALENDAR_STORAGE_UNAVAILABLE", "message": "Calendar storage is unavailable."},
        ) from exc
    finally:
        if conn:
            conn.close()


def _fetch_oracle_calendar_event(user_id, event_id):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                EVENT_ID,
                USER_ID,
                EXTERNAL_SOURCE,
                EXTERNAL_ID,
                TITLE,
                DESCRIPTION,
                TO_CHAR(START_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM') AS START_AT,
                TO_CHAR(END_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM') AS END_AT,
                DURATION_MINUTES,
                IS_MEETING,
                IS_FOCUS_BLOCK,
                ATTENDEE_COUNT,
                TO_CHAR(CREATED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM') AS CREATED_AT,
                TO_CHAR(UPDATED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM') AS UPDATED_AT,
                ROW_VERSION
            FROM CALENDAR_EVENTS
            WHERE USER_ID = :user_id
              AND EVENT_ID = :event_id
            """,
            {"user_id": user_id, "event_id": event_id},
        )
        row = cur.fetchone()
        return _calendar_event_row(row) if row else None
    except oracledb.DatabaseError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "CALENDAR_STORAGE_UNAVAILABLE", "message": "Calendar storage is unavailable."},
        ) from exc
    finally:
        if conn:
            conn.close()


def _update_oracle_calendar_event(user_id, event_id, title):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE CALENDAR_EVENTS
            SET TITLE = :title,
                UPDATED_AT = SYSTIMESTAMP,
                ROW_VERSION = ROW_VERSION + 1
            WHERE USER_ID = :user_id
              AND EVENT_ID = :event_id
            """,
            {"user_id": user_id, "event_id": event_id, "title": title},
        )
        if cur.rowcount != 1:
            conn.rollback()
            return None
        conn.commit()
        return _fetch_oracle_calendar_event(user_id, event_id)
    except oracledb.DatabaseError as exc:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=503,
            detail={"code": "CALENDAR_STORAGE_UNAVAILABLE", "message": "Calendar storage is unavailable."},
        ) from exc
    finally:
        if conn:
            conn.close()


def _delete_oracle_calendar_event(user_id, event_id):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM CALENDAR_EVENTS
            WHERE USER_ID = :user_id
              AND EVENT_ID = :event_id
            """,
            {"user_id": user_id, "event_id": event_id},
        )
        conn.commit()
    except oracledb.DatabaseError as exc:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=503,
            detail={"code": "CALENDAR_STORAGE_UNAVAILABLE", "message": "Calendar storage is unavailable."},
        ) from exc
    finally:
        if conn:
            conn.close()


def _calendar_event_row(row):
    return {
        "event_id": row[0],
        "id": row[0],
        "user_id": row[1],
        "external_source": row[2],
        "external_id": row[3],
        "title": row[4],
        "description": str(row[5] or ""),
        "start_at": row[6],
        "end_at": row[7],
        "duration_minutes": row[8] or 0,
        "is_meeting": bool(row[9]),
        "is_focus_block": bool(row[10]),
        "attendee_count": row[11] or 0,
        "created_at": row[12],
        "updated_at": row[13],
        "row_version": row[14] or 1,
    }


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


def _datetime_or_none(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "calendar event timestamps must use ISO format."},
        ) from exc


def _max_text(value, max_length):
    text = str(value or "").strip()
    return text[:max_length]


def _oracle_error_message(exc):
    error = exc.args[0] if getattr(exc, "args", None) else exc
    message = getattr(error, "message", None)
    code = getattr(error, "code", None)
    if message and code:
        return f"ORA-{code}: {message}"
    return str(message or exc)


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


def _exception_message(exc):
    detail = getattr(exc, "detail", None)
    if isinstance(detail, dict):
        return detail.get("error") or detail.get("message") or str(detail)
    if detail:
        return str(detail)
    return str(exc) or exc.__class__.__name__


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
