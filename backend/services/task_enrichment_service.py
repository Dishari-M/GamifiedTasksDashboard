import asyncio
import time
import threading
from datetime import datetime, timezone

import oracledb
from fastapi import HTTPException

from config import get_oci_genai_model_id
from db import get_connection
from repositories import ai_run_repository, task_repository, task_enrichment_repository
from services.oracle_task_service import create_oracle_task, update_oracle_task
from services import task_enrichment_log_store
from services.xp_service import xp_from_tshirt_size


POLL_SECONDS = 1.25
RUN_TYPE = "TASK_ENRICHMENT"
MAX_FILE_LOG_LINES_PER_POLL = 100
TERMINAL_STATUSES = task_enrichment_repository.TERMINAL_STATUSES
_ACTIVE_WORKER_JOB_IDS = set()
_ACTIVE_WORKER_LOCK = threading.Lock()


def start_task_enrichment(codex_config, payload, user_id):
    data = dict(payload or {})
    source = str(data.get("source") or data.get("external_source") or "").strip()
    external_id = str(data.get("externalId") or data.get("external_id") or "").strip().upper()
    code_base_path = str(data.get("codeBaseLocation") or data.get("code_base_path") or "").strip()
    memory_bank_path = str(data.get("memoryBankLocation") or data.get("memory_bank_path") or "").strip()
    skill_path = str(data.get("skillLocation") or data.get("skill_path") or "").strip()
    existing_task_id = _payload_task_id(data)

    if source != "Jira":
        raise HTTPException(status_code=400, detail={"code": "INVALID_SOURCE", "message": "AI enrichment is only available for Jira tasks."})
    if not external_id:
        raise HTTPException(status_code=400, detail={"code": "MISSING_EXTERNAL_ID", "message": "External ID is required for Jira AI enrichment."})
    if not code_base_path:
        raise HTTPException(status_code=400, detail={"code": "MISSING_CODE_BASE_LOCATION", "message": "Code Base Location is required for Jira AI enrichment."})

    jira_key = codex_config.normalize_jira_key(external_id)
    try:
        resolved_code_base_path = str(codex_config.validate_rca_paths(code_base_path))
        resolved_memory_bank_path = str(codex_config.validate_rca_memory_bank_path(memory_bank_path) or "")
        resolved_skill_path = str(codex_config.validate_rca_skill_path(skill_path) or "")
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_RCA_LOCATION", "message": str(exc)}) from exc

    data["source"] = "Jira"
    data["externalId"] = jira_key
    data["codeBaseLocation"] = resolved_code_base_path
    data["memoryBankLocation"] = resolved_memory_bank_path
    data["skillLocation"] = resolved_skill_path
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        task_enrichment_repository.ensure_schema(cur)
        _fail_orphaned_active_jobs(cur, user_id)
        existing = task_repository.fetch_task_by_external_identity_for_update(cur, user_id, "Jira", jira_key)
        if existing:
            if existing_task_id is None:
                raise HTTPException(
                    status_code=409,
                    detail={"code": "DUPLICATE_EXTERNAL_TASK", "message": "A task with this Jira external ID already exists."},
                )
            if int(existing["task_id"]) != existing_task_id:
                raise HTTPException(
                    status_code=409,
                    detail={"code": "TASK_JIRA_MISMATCH", "message": "The selected task does not match this Jira external ID."},
                )
            data["existingTaskId"] = existing_task_id
            data["taskId"] = existing_task_id
        elif existing_task_id is not None:
            raise HTTPException(
                status_code=404,
                detail={"code": "TASK_NOT_FOUND", "message": "The Jira task was not found for this user."},
            )
        active_job = task_enrichment_repository.fetch_active_job_by_external_identity(cur, user_id, "Jira", jira_key)
        if active_job:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "ENRICHMENT_ALREADY_RUNNING",
                    "message": "AI enrichment is already running for this Jira. Wait for it to finish or fail before starting another one.",
                    "job_id": active_job.get("enrichment_job_id") or active_job.get("id"),
                },
            )
        job_id = task_enrichment_repository.insert_job(cur, user_id, data)
        conn.commit()
        _log(user_id, job_id, "Queued Jira AI enrichment.")
        job = task_enrichment_repository.fetch_job(cur, user_id, job_id)
        _attach_logs(job)
    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except oracledb.DatabaseError as exc:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=503, detail="Task enrichment storage is unavailable.") from exc
    finally:
        if conn:
            conn.close()

    _register_active_worker(job_id)
    thread = threading.Thread(target=_run_task_enrichment_worker, args=(codex_config, user_id, job_id), daemon=True)
    thread.start()
    return job


def list_task_enrichments(user_id, limit=20):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        task_enrichment_repository.ensure_schema(cur)
        _fail_orphaned_active_jobs(cur, user_id)
        conn.commit()
        return {"items": task_enrichment_repository.list_jobs(cur, user_id, limit)}
    except oracledb.DatabaseError as exc:
        raise HTTPException(status_code=503, detail="Task enrichment storage is unavailable.") from exc
    finally:
        if conn:
            conn.close()


def get_task_enrichment(job_id, user_id):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        task_enrichment_repository.ensure_schema(cur)
        _fail_orphaned_active_jobs(cur, user_id)
        conn.commit()
        job = task_enrichment_repository.fetch_job(cur, user_id, int(job_id))
        if not job:
            raise HTTPException(status_code=404, detail={"code": "ENRICHMENT_JOB_NOT_FOUND", "message": "Task enrichment job was not found."})
        _hydrate_saved_enrichment_result(cur, user_id, job)
        _attach_logs(job)
        return job
    except HTTPException:
        raise
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ENRICHMENT_JOB_ID", "message": "Invalid enrichment job id."}) from exc
    except oracledb.DatabaseError as exc:
        raise HTTPException(status_code=503, detail="Task enrichment storage is unavailable.") from exc
    finally:
        if conn:
            conn.close()


def _run_task_enrichment_worker(codex_config, user_id, job_id):
    ai_run_id = None
    try:
        job = _with_job(user_id, job_id)
        if not job:
            return
        if str(job.get("status") or "").upper() in TERMINAL_STATUSES:
            return
        request = dict(job.get("request") or {})
        jira_key = job["external_id"]
        code_base_path = job["code_base_path"]
        memory_bank_path = request.get("memoryBankLocation") or request.get("memory_bank_path") or ""
        skill_path = request.get("skillLocation") or request.get("skill_path") or ""
        existing_task_id = _payload_task_id(request)

        ai_run_id = _start_ai_run(user_id, job_id, request)
        _mark_running(user_id, job_id, ai_run_id)
        _log(user_id, job_id, "Fetching Jira fields.")
        fields = _fetch_jira_fields(codex_config, jira_key)
        _set_jira_fields(user_id, job_id, fields)
        _log(user_id, job_id, f"Fetched Jira fields for {jira_key}.")

        additional_context = _additional_context(request, fields)
        priority = fields.get("priority") or request.get("priority") or "Medium"
        _log(user_id, job_id, "Starting Jira RCA job.")
        if memory_bank_path:
            _log(user_id, job_id, f"Using memory-bank: {memory_bank_path}")
        else:
            _log(user_id, job_id, "No memory-bank selected; Codex will infer context from Jira and the codebase.")
        if skill_path:
            _log(user_id, job_id, f"Using RCA skill: {skill_path}")
        else:
            _log(user_id, job_id, "No RCA skill selected; Codex will use the default RCA output contract.")
        rca_job = codex_config.start_rca_job(
            jira_key,
            additional_context,
            user_id=str(user_id),
            priority=priority,
            code_base_path=code_base_path,
            memory_bank_path=memory_bank_path,
            skill_path=skill_path,
        )
        rca_result = _poll_rca_job(codex_config, user_id, job_id, rca_job["job_id"])
        _log(user_id, job_id, "Preparing enriched task.")

        final_result = _build_final_result(codex_config, jira_key, fields, rca_result)
        task = _build_task_payload(request, fields, final_result, job_id)
        if existing_task_id:
            saved_task = update_oracle_task(existing_task_id, task, user_id)
            task_id = saved_task.get("task_id") or saved_task.get("id")
        else:
            saved_task = create_oracle_task(task, user_id)
            task_id = saved_task.get("task_id") or saved_task.get("id")

        _complete_job(user_id, job_id, task_id, final_result)
        if ai_run_id:
            _update_ai_run(ai_run_id, "SUCCEEDED", {"job_id": job_id, "task_id": task_id, **final_result})
        action = "updated" if existing_task_id else "added"
        _log(user_id, job_id, f"Task {task_id} {action} successfully after AI enrichment.")
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
        status = "AUTH_REQUIRED" if detail.get("code") == "JIRA_MCP_AUTH_REQUIRED" else "FAILED"
        _fail_job(user_id, job_id, status, detail.get("code") or exc.__class__.__name__, detail.get("message") or str(exc.detail))
        if ai_run_id:
            _update_ai_run(ai_run_id, "FAILED", error_code=detail.get("code") or exc.__class__.__name__, error_message=detail.get("message") or str(exc.detail))
    except Exception as exc:
        _fail_job(user_id, job_id, "FAILED", exc.__class__.__name__, str(exc))
        if ai_run_id:
            _update_ai_run(ai_run_id, "FAILED", error_code=exc.__class__.__name__, error_message=str(exc))
    finally:
        _unregister_active_worker(job_id)


def _register_active_worker(job_id):
    with _ACTIVE_WORKER_LOCK:
        _ACTIVE_WORKER_JOB_IDS.add(int(job_id))


def _unregister_active_worker(job_id):
    with _ACTIVE_WORKER_LOCK:
        _ACTIVE_WORKER_JOB_IDS.discard(int(job_id))


def _payload_task_id(data):
    value = (
        (data or {}).get("existingTaskId")
        or (data or {}).get("existing_task_id")
        or (data or {}).get("taskId")
        or (data or {}).get("task_id")
    )
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_TASK_ID", "message": "Task ID must be numeric."}) from exc


def _is_active_worker(job_id):
    with _ACTIVE_WORKER_LOCK:
        return int(job_id) in _ACTIVE_WORKER_JOB_IDS


def _fail_orphaned_active_jobs(cur, user_id):
    message = "The backend was restarted or the enrichment worker is no longer running. Please start AI enrichment again."
    for job in task_enrichment_repository.list_active_jobs(cur, user_id):
        job_id = job.get("enrichment_job_id") or job.get("id")
        if _is_active_worker(job_id):
            continue
        task_enrichment_log_store.append_log(user_id, job_id, message, "ERROR")
        task_enrichment_repository.mark_failed(cur, user_id, job_id, "FAILED", "ENRICHMENT_WORKER_NOT_RUNNING", message)


def _fetch_jira_fields(codex_config, jira_key):
    output = _run_async(codex_config.run_codex_async(codex_config.build_jira_task_fields_prompt(jira_key)))
    if codex_config.looks_like_mcp_auth_cancelled(output):
        codex_config.raise_mcp_auth_required(jira_key)
    return codex_config.normalize_jira_task_fields(jira_key, output)


def _poll_rca_job(codex_config, user_id, enrichment_job_id, rca_job_id):
    copied_log_count = 0
    while True:
        rca_job = codex_config.get_rca_job(rca_job_id)
        logs = list(rca_job.get("logs") or [])
        new_logs = logs[copied_log_count:]
        if new_logs:
            _log_many(user_id, enrichment_job_id, new_logs[:MAX_FILE_LOG_LINES_PER_POLL])
            if len(new_logs) > MAX_FILE_LOG_LINES_PER_POLL:
                skipped = len(new_logs) - MAX_FILE_LOG_LINES_PER_POLL
                _log(user_id, enrichment_job_id, f"Skipped {skipped} verbose console line(s) in this polling interval.", level="INFO")
        copied_log_count = len(logs)
        status = rca_job.get("status")
        if status not in getattr(codex_config, "ACTIVE_RCA_STATUSES", {"queued", "running"}):
            if status == "completed":
                result = rca_job.get("result") or {}
                _set_rca_result(user_id, enrichment_job_id, result)
                return result
            error = rca_job.get("error") or "RCA job failed."
            if status == "auth_required":
                raise HTTPException(status_code=409, detail={"code": "JIRA_MCP_AUTH_REQUIRED", "message": error})
            raise RuntimeError(error)
        time.sleep(POLL_SECONDS)


def _build_final_result(codex_config, jira_key, fields, rca_result):
    raw_output = str(rca_result.get("root_cause_analysis") or "")
    sizing = _coerce_sizing(
        rca_result.get("tshirt_sizing")
        or rca_result.get("tshirtSizing")
        or rca_result.get("jira_tshirt_sizing")
        or rca_result.get("jiraTshirtSizing")
    )
    reason = _extract_section(
        codex_config,
        raw_output,
        "Root Cause",
        ("Affected Modules", "Affected Files", "Code Fix Suggestion", "Code Suggestion", "Evidence", "Open Questions"),
    )
    code_suggestion = _extract_section(codex_config, raw_output, "Code Fix Suggestion", ("Evidence", "Open Questions"))
    if not code_suggestion:
        code_suggestion = _extract_section(codex_config, raw_output, "Code Suggestion", ("Evidence", "Open Questions"))
    affected_files = _extract_affected_files(codex_config, raw_output)
    if not affected_files:
        affected_files = _coerce_affected_files(sizing.get("affected_files"))
    affected_file_count = _affected_file_count(affected_files, sizing.get("affected_files"))
    size = str(sizing.get("size") or "").strip().upper()
    xp_value = xp_from_tshirt_size(size) or 60
    final_result = {
        "jira_key": jira_key,
        "jira_fields": fields,
        "root_cause_analysis": raw_output,
        "rca_reason": reason or raw_output[:1000],
        "affected_files": affected_files,
        "affected_file_count": affected_file_count,
        "code_suggestion": code_suggestion,
        "tshirt_sizing": sizing,
        "jira_tshirt_sizing": sizing,
        "tshirt_size": size,
        "tshirt_justification": sizing.get("reason") or "",
        "xp_value": xp_value,
        "elapsed_seconds": rca_result.get("elapsed_seconds"),
    }
    return final_result


def _hydrate_saved_enrichment_result(cur, user_id, job):
    result = dict(job.get("rca_result") or {})
    task = None
    task_id = job.get("task_id") or job.get("taskId")
    if task_id:
        task = task_repository.fetch_task(cur, user_id, task_id, datetime.now(timezone.utc).date().isoformat())

    raw_output = str(
        result.get("root_cause_analysis")
        or result.get("rootCauseAnalysis")
        or result.get("rca_raw_output")
        or result.get("rcaRawOutput")
        or (task or {}).get("rca_raw_output")
        or (task or {}).get("rcaRawOutput")
        or ""
    )
    if raw_output and not result.get("root_cause_analysis"):
        result["root_cause_analysis"] = raw_output

    if task:
        result.setdefault("rca_reason", task.get("rca_reason") or task.get("rcaReason") or "")
        result.setdefault("code_suggestion", task.get("rca_code_suggestion") or task.get("rcaCodeSuggestion") or "")
        result.setdefault("affected_files", _coerce_affected_files(task.get("rca_affected_files") or task.get("rcaAffectedFiles")))
        result.setdefault("tshirt_size", task.get("rca_tshirt_size") or task.get("rcaTshirtSize") or "")
        result.setdefault("tshirt_justification", task.get("rca_tshirt_justification") or task.get("rcaTshirtJustification") or "")

    if raw_output:
        parsed_reason = _extract_markdown_section(
            raw_output,
            "Root Cause",
            ("Affected Modules", "Affected Files", "Code Fix Suggestion", "Code Suggestion", "Evidence", "Open Questions"),
        )
        current_reason = str(result.get("rca_reason") or "").strip()
        if parsed_reason and (not current_reason or _contains_later_rca_heading(current_reason)):
            result["rca_reason"] = parsed_reason
        elif not current_reason:
            result["rca_reason"] = raw_output[:1000]

        if not _coerce_affected_files(result.get("affected_files")):
            result["affected_files"] = _extract_affected_files_from_text(raw_output)
        if not str(result.get("code_suggestion") or "").strip():
            result["code_suggestion"] = _extract_markdown_section(
                raw_output,
                "Code Fix Suggestion",
                ("Evidence", "Open Questions"),
            ) or _extract_markdown_section(
                raw_output,
                "Code Suggestion",
                ("Evidence", "Open Questions"),
            )

    result["affected_files"] = _coerce_affected_files(result.get("affected_files"))
    job["rca_result"] = result
    job["rcaResult"] = result
    if task:
        job["saved_task"] = task
        job["savedTask"] = task
    return job


def _build_task_payload(request, fields, final_result, job_id):
    labels = fields.get("labels") if isinstance(fields.get("labels"), list) else []
    affected_files = final_result.get("affected_files") or []
    affected_file_count = final_result.get("affected_file_count")
    if affected_file_count is None:
        affected_file_count = len(affected_files)
    return {
        "title": fields.get("title") or request.get("title") or request.get("externalId") or "Jira Task",
        "description": fields.get("description") or request.get("description") or "",
        "source": "Jira",
        "externalId": request.get("externalId") or request.get("external_id") or fields.get("jira_key"),
        "type": fields.get("type") or request.get("type") or "Task",
        "priority": fields.get("priority") or request.get("priority") or "Medium",
        "status": request.get("status") or "To Do",
        "dueDate": request.get("dueDate") or request.get("due_at"),
        "startDate": request.get("startDate") or request.get("start_at"),
        "estimatedMinutes": request.get("estimatedMinutes") or request.get("estimated_minutes") or 60,
        "actualMinutes": request.get("actualMinutes") or request.get("actual_minutes") or 0,
        "labels": ", ".join(labels) if labels else request.get("labels", ""),
        "notes": request.get("notes") or "",
        "workingToday": bool(request.get("workingToday", True)),
        "runAiEnrichment": False,
        "rcaTshirtSize": final_result.get("tshirt_size"),
        "rcaFileChangeCount": affected_file_count,
        "rcaComplexitySource": "RCA",
        "rcaComplexityAt": datetime.now(timezone.utc).isoformat(),
        "xp": final_result.get("xp_value"),
        "rcaReason": final_result.get("rca_reason"),
        "rcaAffectedFiles": [item.get("path") or str(item) for item in affected_files],
        "rcaCodeSuggestion": final_result.get("code_suggestion"),
        "rcaRawOutput": final_result.get("root_cause_analysis"),
        "rcaTshirtJustification": final_result.get("tshirt_justification"),
        "sourceEnrichmentJobId": job_id,
    }


def _additional_context(request, fields):
    parts = []
    if fields.get("title"):
        parts.append(f"Jira title: {fields['title']}")
    if fields.get("description"):
        parts.append(f"One-line description: {fields['description']}")
    if request.get("notes"):
        parts.append(f"User notes: {request['notes']}")
    return "\n".join(parts)


def _extract_section(codex_config, text, heading, next_headings):
    try:
        section = codex_config.extract_section(text, heading, next_headings)
        if section:
            return section
    except Exception:
        pass
    return _extract_markdown_section(text, heading, next_headings)


def _extract_affected_files(codex_config, text):
    section = _extract_section(codex_config, text, "Affected Files", ("Code Fix Suggestion", "Code Suggestion", "Evidence", "Open Questions"))
    return _affected_files_from_section(section)


def _extract_affected_files_from_text(text):
    section = _extract_markdown_section(text, "Affected Files", ("Code Fix Suggestion", "Code Suggestion", "Evidence", "Open Questions"))
    return _affected_files_from_section(section)


def _affected_files_from_section(section):
    files = []
    for line in section.splitlines():
        item = line.strip().lstrip("-*").strip()
        if not item:
            continue
        if "->" in item:
            path, reason = item.split("->", 1)
        elif " - " in item:
            path, reason = item.split(" - ", 1)
        else:
            path, reason = item, ""
        path, location = _parse_file_reference(path)
        if "/" in path or "\\" in path or "." in path:
            entry = {"path": path, "reason": reason.strip()}
            if location:
                entry["location"] = location
            files.append(entry)
    return files


def _extract_markdown_section(text, heading, next_headings):
    if not text:
        return ""
    heading_pattern = _heading_pattern(heading)
    match = heading_pattern.search(text)
    if not match:
        return ""

    start = match.end()
    end = len(text)
    for next_heading in next_headings:
        next_match = _heading_pattern(next_heading).search(text, start)
        if next_match:
            end = min(end, next_match.start())
    return text[start:end].strip()


def _heading_pattern(heading):
    import re

    return re.compile(rf"(?im)^\s*(?:#+\s*)?(?:\*\*)?\s*{re.escape(heading)}\s*(?:\*\*)?\s*:?\s*$")


def _parse_file_reference(value):
    import re

    text = str(value or "").strip(" `")
    match = re.match(r"\[([^\]]+)\]\(([^)]+)\)", text)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return text, ""


def _coerce_sizing(value):
    return dict(value) if isinstance(value, dict) else {}


def _coerce_affected_files(value):
    if isinstance(value, list):
        return [{"path": item.get("path") or str(item), "reason": item.get("reason") or ""} if isinstance(item, dict) else {"path": str(item), "reason": ""} for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [{"path": line.strip().lstrip("-*").strip(), "reason": ""} for line in value.splitlines() if line.strip().lstrip("-*").strip()]
    return []


def _contains_later_rca_heading(value):
    return any(_heading_pattern(heading).search(value) for heading in ("Affected Modules", "Affected Files", "Code Fix Suggestion", "Code Suggestion", "Evidence", "Open Questions"))


def _affected_file_count(affected_files, sizing_affected_files):
    if isinstance(sizing_affected_files, (int, float)):
        return max(0, int(sizing_affected_files))
    if isinstance(sizing_affected_files, list):
        return len(sizing_affected_files)
    return len(affected_files or [])


def _run_async(awaitable):
    return asyncio.run(awaitable)


def _with_job(user_id, job_id):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        task_enrichment_repository.ensure_schema(cur)
        return task_enrichment_repository.fetch_job(cur, user_id, job_id)
    finally:
        if conn:
            conn.close()


def _start_ai_run(user_id, job_id, request):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        task_enrichment_repository.ensure_schema(cur)
        ai_run_id = ai_run_repository.insert_ai_run(cur, user_id, RUN_TYPE, get_oci_genai_model_id(), {"job_id": job_id, "request": request})
        task_enrichment_repository.mark_running(cur, user_id, job_id, ai_run_id)
        conn.commit()
        return ai_run_id
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def _mark_running(user_id, job_id, ai_run_id=None):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        task_enrichment_repository.ensure_schema(cur)
        task_enrichment_repository.mark_running(cur, user_id, job_id, ai_run_id)
        conn.commit()
    finally:
        if conn:
            conn.close()


def _set_jira_fields(user_id, job_id, fields):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        task_enrichment_repository.ensure_schema(cur)
        task_enrichment_repository.set_jira_fields(cur, user_id, job_id, fields)
        conn.commit()
    finally:
        if conn:
            conn.close()


def _set_rca_result(user_id, job_id, result):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        task_enrichment_repository.ensure_schema(cur)
        task_enrichment_repository.set_rca_result(cur, user_id, job_id, result)
        conn.commit()
    finally:
        if conn:
            conn.close()


def _complete_job(user_id, job_id, task_id, result):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        task_enrichment_repository.ensure_schema(cur)
        task_enrichment_repository.mark_succeeded(cur, user_id, job_id, task_id, result)
        conn.commit()
    finally:
        if conn:
            conn.close()


def _fail_job(user_id, job_id, status, error_code, error_message):
    try:
        _log(user_id, job_id, error_message, level="ERROR")
    except Exception:
        pass
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        task_enrichment_repository.ensure_schema(cur)
        task_enrichment_repository.mark_failed(cur, user_id, job_id, status, error_code, error_message)
        conn.commit()
    finally:
        if conn:
            conn.close()


def _log(user_id, job_id, message, level="INFO"):
    task_enrichment_log_store.append_log(user_id, job_id, message, level)


def _log_many(user_id, job_id, messages, level="INFO"):
    if not messages:
        return
    task_enrichment_log_store.append_logs(user_id, job_id, messages, level)


def _attach_logs(job):
    if job:
        job["logs"] = task_enrichment_log_store.read_logs(job.get("enrichment_job_id") or job.get("id"))
    return job


def _update_ai_run(ai_run_id, status, response_payload=None, error_code=None, error_message=None):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        ai_run_repository.update_ai_run(cur, ai_run_id, status, response_payload, error_code, error_message)
        conn.commit()
    finally:
        if conn:
            conn.close()
