from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import tomllib
import uuid
from pathlib import Path
from time import perf_counter

from fastapi import HTTPException

from services.filesystem_task_service import (
    LOCAL_USER_ID,
    find_filesystem_jira_task,
    save_jira_tshirt_sizing,
)


SERVICE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SERVICE_DIR.parent
DEFAULT_CODEX_HOME = Path.home() / ".codex"
RUNTIME_CODEX_HOME = Path(os.getenv("JIRA_RCA_CODEX_HOME", str(DEFAULT_CODEX_HOME)))
CODEX_SCRATCH_DIR = SERVICE_DIR / ".codex-rca-runtime"

CODE_BASE_DIR = Path(os.getenv("RCA_CODE_BASE_DIR", str(PROJECT_ROOT)))
MEMORY_BANK_DIR = Path(os.getenv("RCA_MEMORY_BANK_DIR", str(PROJECT_ROOT / "memory-bank-RCA")))
RCA_SKILL_DIR = Path(os.getenv("RCA_SKILL_DIR", str(PROJECT_ROOT / "skills" / "enterprise-rca")))
RCA_SKILL_FILE = RCA_SKILL_DIR / "SKILL.md"
JIRA_MCP_SERVER = os.getenv("JIRA_MCP_SERVER", "central_jira_confluence")

CODEX_TIMEOUT_SECONDS = max(1, int(os.getenv("CODEX_TIMEOUT_SECONDS", "420")))
CODEX_BYPASS_APPROVALS = os.getenv("CODEX_BYPASS_APPROVALS", "true").strip().lower() not in ("0", "false", "no")
CODEX_AUTO_APPROVE_MCP_TOOLS = os.getenv("CODEX_AUTO_APPROVE_MCP_TOOLS", "true").strip().lower() not in ("0", "false", "no")
CODEX_AUTO_APPROVE_APPS = os.getenv("CODEX_AUTO_APPROVE_APPS", "true").strip().lower() not in ("0", "false", "no")
CODEX_AUTO_APPROVE_APP_IDS = [
    app_id.strip()
    for app_id in os.getenv("CODEX_AUTO_APPROVE_APP_IDS", "").split(",")
    if app_id.strip()
]
MAX_CONCURRENT_CODEX_JOBS = max(1, int(os.getenv("MAX_CONCURRENT_CODEX_JOBS", "2")))
CODEX_QUEUE_TIMEOUT_SECONDS = max(1, int(os.getenv("CODEX_QUEUE_TIMEOUT_SECONDS", "30")))
CODEX_SLOT_POLL_INTERVAL_SECONDS = 0.2
MAX_RCA_JOB_LOG_LINES = max(500, int(os.getenv("MAX_RCA_JOB_LOG_LINES", "5000")))
JIRA_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")
STALE_CODEX_SLOT_SECONDS = max(
    CODEX_TIMEOUT_SECONDS + CODEX_QUEUE_TIMEOUT_SECONDS,
    int(os.getenv("STALE_CODEX_SLOT_SECONDS", "1200")),
)

codex_job_semaphore = asyncio.Semaphore(MAX_CONCURRENT_CODEX_JOBS)
rca_jobs: dict[str, dict] = {}
rca_jobs_lock = threading.Lock()
ACTIVE_RCA_STATUSES = {"queued", "running"}
TERMINAL_RCA_STATUSES = {"completed", "failed", "auth_required", "cancelled"}
TSHIRT_SIZES = ("XS", "S", "M", "L", "XL")


class RcaJobCancelled(Exception):
    pass

JIRA_RCA_SYSTEM_PROMPT_TEMPLATE = """
You are an enterprise Jira root-cause-analysis agent.

MANDATORY SOURCES:
1. Fetch Jira details and Jira comments from MCP server: {jira_mcp_server}.
2. Use the enterprise RCA skill instructions from {rca_skill_file}.
3. Use {memory_bank_dir} as the primary architecture/context reference.
4. Analyze the codebase rooted at {code_base_dir}.

STRICT RULES:
1. Start from the Jira key. Fetch Jira summary, description, status, issue type, priority, components, labels, affects version, fix version, attachments/log snippets if visible, and comments.
2. If Jira includes Affects Version, use it to choose UI code locations according to the RCA skill.
3. Read only the memory-bank files that are relevant to the Jira module and symptom before drawing conclusions.
4. Trace code flow through the most relevant modules and build.gradle dependencies. Stop once there is enough concrete evidence for a root-cause hypothesis and fix.
5. Root cause must identify the specific failing condition in code or data flow, not just the symptom.
6. Cite exact local file paths for affected files and explain why each file matters.
7. If evidence is insufficient, say exactly what is missing and provide the best-supported hypothesis separately.
8. Do not modify files. This service is analysis-only.
9. Do not output markdown code fences around the whole response.
10. Complete the investigation in under 5 minutes. Prefer a concise, evidence-backed RCA over exhaustive repository traversal.
11. Do not print full file contents, SQL blocks, XML blocks, Gradle files, or large snippets to the console. Quote only tiny snippets when necessary.

REPORTING:
Follow the enterprise RCA skill's required workflow and output format.
Do not add a separate one-line Jira description or task-form summary during RCA.
Keep the final answer compact: root cause, affected files, code suggestion, evidence, and open questions only.
"""

JIRA_ONE_LINE_DESCRIPTION_PROMPT = """
You are a Jira description summarizer.

MANDATORY SOURCE:
Fetch the Jira details from MCP server: central_jira_confluence.

STRICT RULES:
1. First fetch the Jira issue with fields: summary,status,assignee,priority.
2. If that succeeds, optionally fetch description too; if description fetch fails or is cancelled, continue using the summary.
3. Summarize the Jira into exactly one plain-language sentence.
4. Keep the sentence specific enough to be useful in a task form.
5. Do not include root cause analysis, affected files, markdown, bullets, labels, or headings.
6. If only the Jira summary is available, summarize from the summary and say only what is supported.
7. Do not say that the MCP call failed if the summary fetch succeeded.
"""


def resolve_codex_path() -> str:
    candidates: list[str] = []

    for executable_name in ("codex.cmd", "codex.exe", "codex"):
        executable_path = shutil.which(executable_name)
        if executable_path and executable_path not in candidates:
            candidates.append(executable_path)

    if not candidates:
        raise RuntimeError("Codex CLI not found in PATH")

    for executable_path in candidates:
        if executable_path.lower().endswith((".cmd", ".exe")):
            return executable_path

    return candidates[0]


def load_text(path: Path) -> str:
    if not path.exists():
        raise RuntimeError(f"Required file not found: {path}")

    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise RuntimeError(f"Required file is empty: {path}")

    return content


def resolve_rca_code_base_dir(code_base_path: str | None = None) -> Path:
    return Path((code_base_path or "").strip() or str(CODE_BASE_DIR)).expanduser().resolve()


def select_rca_workspace_folder(initial_path: str | None = None) -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        raise RuntimeError("Native folder picker is unavailable on this machine.") from exc

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected_path = filedialog.askdirectory(
            title="Select codebase workspace for Jira RCA",
            initialdir=str(resolve_rca_code_base_dir(initial_path)),
            mustexist=True,
        )
    finally:
        root.destroy()

    if not selected_path:
        return ""
    return str(Path(selected_path).expanduser().resolve())


def validate_rca_paths(code_base_path: str | None = None) -> Path:
    code_base_dir = resolve_rca_code_base_dir(code_base_path)
    if not code_base_dir.exists():
        raise RuntimeError(f"Code base directory not found: {code_base_dir}")
    if not code_base_dir.is_dir():
        raise RuntimeError(f"Code base path is not a directory: {code_base_dir}")
    if not MEMORY_BANK_DIR.exists():
        raise RuntimeError(f"Memory-bank directory not found: {MEMORY_BANK_DIR}")
    if not RCA_SKILL_FILE.exists():
        raise RuntimeError(f"Enterprise RCA skill not found: {RCA_SKILL_FILE}")
    return code_base_dir


def normalize_jira_key(jira_key: str) -> str:
    normalized = jira_key.strip().upper()
    if not JIRA_KEY_PATTERN.match(normalized):
        raise HTTPException(status_code=400, detail="jira_key must look like HEPRT-123")
    return normalized


def build_jira_rca_prompt(jira_key: str, additional_context: str = "", code_base_path: str | None = None) -> str:
    code_base_dir = validate_rca_paths(code_base_path)
    rca_skill = load_text(RCA_SKILL_FILE)
    context_block = additional_context.strip() or "N/A"
    system_prompt = JIRA_RCA_SYSTEM_PROMPT_TEMPLATE.format(
        jira_mcp_server=JIRA_MCP_SERVER,
        rca_skill_file=RCA_SKILL_FILE,
        memory_bank_dir=MEMORY_BANK_DIR,
        code_base_dir=code_base_dir,
    )

    return f"""
{system_prompt}

===== RUNTIME CONFIG =====
Jira MCP server: {JIRA_MCP_SERVER}
Code base path: {code_base_dir}
Memory-bank path: {MEMORY_BANK_DIR}
Enterprise RCA skill path: {RCA_SKILL_FILE}

===== ENTERPRISE RCA SKILL =====
{rca_skill}

===== JIRA REQUEST =====
Jira key: {jira_key}

===== ADDITIONAL CONTEXT =====
{context_block}

Now fetch the Jira details and comments using the {JIRA_MCP_SERVER} MCP server, analyze the codebase at {code_base_dir}, and produce the requested output format.
"""


def build_jira_one_line_description_prompt(jira_key: str) -> str:
    return f"""
{JIRA_ONE_LINE_DESCRIPTION_PROMPT}

===== RUNTIME CONFIG =====
Jira MCP server: {JIRA_MCP_SERVER}

===== JIRA REQUEST =====
Jira key: {jira_key}

Fetch the Jira description using the {JIRA_MCP_SERVER} MCP server and output exactly one sentence of the description.
Prefer a successful summary-only fetch over failing the task because description is unavailable.
"""


def build_jira_task_fields_prompt(jira_key: str) -> str:
    return f"""
You are a Jira task-field fetcher.

MANDATORY SOURCE:
Fetch Jira details from MCP server: {JIRA_MCP_SERVER}.

STRICT RULES:
1. Fetch Jira {jira_key} with at least summary, description, priority, labels, and issuetype if available.
2. Return only one valid JSON object. Do not wrap it in markdown.
3. The JSON object must have these keys:
   - title: string
   - description: string, summarized to exactly one short sentence
   - priority: one of "Critical", "High", "Medium", "Low"
   - labels: array of strings
   - type: one of "Task", "Bug", "Epic", "Review", "Meeting"
4. If Jira priority is absent, use "Medium".
5. If Jira labels are absent, return an empty array.
6. Map Jira issue types to the closest allowed type. Use "Bug" only for bug-like issues, "Epic" for epics, otherwise "Task".

===== RUNTIME CONFIG =====
Jira MCP server: {JIRA_MCP_SERVER}

===== JIRA REQUEST =====
Jira key: {jira_key}
"""


def ensure_runtime_codex_home() -> Path:
    RUNTIME_CODEX_HOME.mkdir(parents=True, exist_ok=True)
    CODEX_SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

    for directory_name in ("log", "sessions", "tmp", "memories", "locks"):
        (CODEX_SCRATCH_DIR / directory_name).mkdir(parents=True, exist_ok=True)

    for file_name in ("config.toml", "auth.json"):
        source_path = DEFAULT_CODEX_HOME / file_name
        target_path = RUNTIME_CODEX_HOME / file_name

        if not source_path.exists():
            continue

        if not target_path.exists() or source_path.stat().st_mtime > target_path.stat().st_mtime:
            shutil.copy2(source_path, target_path)

    return RUNTIME_CODEX_HOME


def strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return stripped


def extract_section(text: str, heading: str, next_headings: tuple[str, ...]) -> str:
    start_match = re.search(rf"(?im)^\s*{re.escape(heading)}\s*$", text)
    if not start_match:
        return ""

    start = start_match.end()
    end = len(text)
    for next_heading in next_headings:
        next_match = re.search(rf"(?im)^\s*{re.escape(next_heading)}\s*$", text[start:])
        if next_match:
            end = min(end, start + next_match.start())

    return text[start:end].strip()


def normalize_one_line_description(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return ""

    first_line = lines[0]
    first_line = re.sub(r"^\s*(ONE LINE JIRA DESCRIPTION|DESCRIPTION)\s*:?\s*", "", first_line, flags=re.IGNORECASE)
    return first_line.strip()


def extract_json_object(output: str) -> dict:
    stripped = strip_code_fences(output).strip()
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Codex did not return a JSON object.")

    parsed = json.loads(stripped[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Codex JSON response was not an object.")
    return parsed


def normalize_jira_priority(priority: str) -> str:
    normalized = str(priority or "").strip().lower()
    if normalized in {"critical", "blocker", "highest", "p0"}:
        return "Critical"
    if normalized in {"high", "major", "p1"}:
        return "High"
    if normalized in {"low", "minor", "lowest", "trivial", "p3", "p4"}:
        return "Low"
    return "Medium"


def normalize_jira_task_type(task_type: str) -> str:
    normalized = str(task_type or "").strip().lower()
    if "bug" in normalized or "defect" in normalized:
        return "Bug"
    if "epic" in normalized:
        return "Epic"
    if "review" in normalized or "pull request" in normalized or normalized == "pr":
        return "Review"
    if "meeting" in normalized:
        return "Meeting"
    return "Task"


def normalize_jira_task_fields(jira_key: str, output: str) -> dict:
    payload = extract_json_object(output)
    title = str(payload.get("title") or payload.get("summary") or "").strip()
    description = normalize_one_line_description(str(payload.get("description") or ""))
    raw_labels = payload.get("labels") or []
    labels = raw_labels if isinstance(raw_labels, list) else str(raw_labels).split(",")
    labels = [str(label).strip() for label in labels if str(label).strip()]

    return {
        "jira_key": jira_key,
        "title": title,
        "description": description,
        "priority": normalize_jira_priority(payload.get("priority")),
        "labels": labels,
        "type": normalize_jira_task_type(payload.get("type") or payload.get("issue_type") or payload.get("issuetype")),
    }


def _extract_code_fix_section(output: str) -> str:
    section = extract_section(
        output,
        "CODE FIX SUGGESTION",
        ("EVIDENCE", "OPEN QUESTIONS", "JIRA DETAILS", "ROOT CAUSE ANALYSIS", "AFFECTED MODULES", "AFFECTED FILES"),
    )
    return section or output


def _estimate_affected_file_count(output: str) -> int:
    file_pattern = re.compile(
        r"(?i)\b[\w./\\-]+\.(?:java|kt|js|jsx|ts|tsx|py|sql|xml|json|yaml|yml|gradle|properties|css|scss|html)\b"
    )
    files = {match.group(0).strip("`.,;:()[]{}") for match in file_pattern.finditer(output)}
    return len(files)


def _estimate_suggested_change_count(output: str) -> int:
    code_fix = _extract_code_fix_section(output)
    bullet_count = len(re.findall(r"(?m)^\s*(?:[-*]|\d+\.)\s+\S", code_fix))
    action_count = len(
        re.findall(
            r"(?i)\b(add|update|change|modify|replace|remove|guard|validate|fallback|refactor|test|handle|ensure|map|persist)\b",
            code_fix,
        )
    )
    return max(1, min(10, bullet_count or round(action_count / 3) or 1))


def _detect_sizing_risk_signals(output: str) -> list[str]:
    text = output.lower()
    signals: list[str] = []
    signal_rules = [
        ("database or migration touchpoint", ("database", "schema", "migration", "sql", "query", "table")),
        ("API or contract change", ("api", "endpoint", "request", "response", "contract", "payload")),
        ("cross-module flow", ("cross-module", "multiple modules", "service layer", "controller", "frontend", "backend")),
        ("security or permission logic", ("auth", "permission", "role", "token", "sso", "security")),
        ("regression coverage required", ("regression", "unit test", "integration test", "test coverage", "coverage")),
        ("async or concurrency behavior", ("async", "thread", "queue", "race", "lock", "timeout", "retry")),
    ]
    for label, needles in signal_rules:
        if any(needle in text for needle in needles):
            signals.append(label)
    return signals[:5]


def calculate_jira_tshirt_sizing(jira_key: str, priority: str, rca_output: str) -> dict:
    normalized_priority = normalize_jira_priority(priority)
    priority_points = {"Low": 8, "Medium": 16, "High": 24, "Critical": 32}.get(normalized_priority, 16)
    affected_files = _estimate_affected_file_count(rca_output)
    suggested_changes = _estimate_suggested_change_count(rca_output)
    risk_signals = _detect_sizing_risk_signals(rca_output)

    file_points = min(28, affected_files * 5)
    change_points = min(24, suggested_changes * 4)
    risk_points = min(22, len(risk_signals) * 5)
    score = min(100, priority_points + file_points + change_points + risk_points)

    if score >= 78:
        size = "XL"
    elif score >= 58:
        size = "L"
    elif score >= 37:
        size = "M"
    elif score >= 20:
        size = "S"
    else:
        size = "XS"

    fallback_reason = "limited explicit code-change evidence"
    strongest_factor = (
        f"{affected_files} affected file(s)"
        if affected_files
        else f"{suggested_changes} concrete suggested change(s)"
        if suggested_changes
        else fallback_reason
    )
    risk_phrase = f" and risk signals around {', '.join(risk_signals[:3])}" if risk_signals else ""

    return {
        "jira_key": jira_key,
        "size": size,
        "score": score,
        "priority": normalized_priority,
        "affected_files": affected_files,
        "suggested_changes": suggested_changes,
        "risk_signals": risk_signals,
        "reason": (
            f"{normalized_priority} priority contributes {priority_points} base points; "
            f"the RCA indicates {strongest_factor}{risk_phrase}. "
            f"Composite score {score}/100 maps to {size}."
        ),
    }


def build_jira_tshirt_sizing(jira_key: str, rca_output: str, user_id: str = LOCAL_USER_ID, priority: str | None = None) -> dict:
    task = None
    try:
        task = find_filesystem_jira_task(jira_key, user_id)
    except Exception:
        task = None
    task_priority = priority or (task or {}).get("priority") or "Medium"
    sizing = calculate_jira_tshirt_sizing(jira_key, task_priority, rca_output)
    try:
        save_jira_tshirt_sizing(jira_key, sizing, user_id)
    except Exception:
        pass
    return sizing


RCA_HEADING_PATTERN = re.compile(
    r"(?im)^\s*(?:#{1,6}\s*)?"
    r"(?:JIRA DETAILS|ROOT CAUSE ANALYSIS|ROOT CAUSE|AFFECTED MODULES|"
    r"AFFECTED FILES|CODE FIX SUGGESTION|EVIDENCE|OPEN QUESTIONS)\b"
)

AUTH_REQUIRED_PATTERN = re.compile(
    r"(?i)("
    r"jira mcp authentication is required|"
    r"authentication is required for .*jira|"
    r"authentication required.*jira|"
    r"jira.*authentication required|"
    r"jira.*not authorized|"
    r"jira.*unauthorized|"
    r"jira.*login required|"
    r"jira.*sso required|"
    r"central_jira_confluence.*(?:auth|login|sso).*required|"
    r"mcp.*jira.*(?:cancelled|canceled)"
    r")"
)


def looks_like_rca_output(output: str) -> bool:
    headings = {match.group(0).lstrip("#").strip().upper() for match in RCA_HEADING_PATTERN.finditer(output)}
    return len(headings) >= 2 or "ROOT CAUSE" in output.upper() and "AFFECTED FILES" in output.upper()


def looks_like_mcp_auth_cancelled(output: str) -> bool:
    if looks_like_rca_output(output):
        return False

    return bool(AUTH_REQUIRED_PATTERN.search(output))


def get_rca_job_logs(job_id: str) -> list[str]:
    with rca_jobs_lock:
        return list(rca_jobs.get(job_id, {}).get("logs", []))


def extract_streamed_rca_output(logs: list[str]) -> str:
    content_lines = [
        line.rstrip()
        for line in logs
        if not line.startswith(
            (
                "Queued Jira RCA job.",
                "Starting Codex CLI RCA process.",
                "Codebase:",
                "Memory-bank:",
                "Skill:",
                "MCP server:",
                "Codex execution slot acquired.",
            )
        )
    ]
    content = "\n".join(content_lines).strip()
    if not looks_like_rca_output(content):
        return ""

    first_heading = RCA_HEADING_PATTERN.search(content)
    if first_heading:
        content = content[first_heading.start() :].strip()

    return strip_code_fences(content)


def raise_mcp_auth_required(jira_key: str) -> None:
    raise HTTPException(
        status_code=409,
        detail={
            "code": "JIRA_MCP_AUTH_REQUIRED",
            "message": (
                f"Jira MCP authentication is required for {jira_key}. "
                "Start the SSO login flow, complete the browser sign-in, then retry Generate by AI."
            ),
        },
    )


def acquire_codex_slot(should_cancel=None) -> Path:
    ensure_runtime_codex_home()
    locks_dir = CODEX_SCRATCH_DIR / "locks"
    deadline = perf_counter() + CODEX_QUEUE_TIMEOUT_SECONDS
    owner_token = f"{os.getpid()}-{uuid.uuid4().hex}"

    while perf_counter() < deadline:
        if should_cancel and should_cancel():
            raise RcaJobCancelled()
        cleanup_stale_codex_slots()
        for slot_index in range(MAX_CONCURRENT_CODEX_JOBS):
            slot_path = locks_dir / f"slot-{slot_index}"
            try:
                slot_path.mkdir()
                (slot_path / "owner.txt").write_text(owner_token, encoding="utf-8")
                return slot_path
            except FileExistsError:
                continue
        time.sleep(CODEX_SLOT_POLL_INTERVAL_SECONDS)

    raise TimeoutError("No Codex execution slot available. Please retry shortly.")


def release_codex_slot(slot_path: Path | None) -> None:
    if slot_path:
        shutil.rmtree(slot_path, ignore_errors=True)


def is_process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return str(pid) in result.stdout
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def cleanup_stale_codex_slots() -> None:
    locks_dir = CODEX_SCRATCH_DIR / "locks"
    if not locks_dir.exists():
        return

    now = time.time()
    for slot_path in locks_dir.glob("slot-*"):
        if not slot_path.is_dir():
            continue

        owner_path = slot_path / "owner.txt"
        owner_text = ""
        try:
            owner_text = owner_path.read_text(encoding="utf-8").strip()
            slot_age = now - slot_path.stat().st_mtime
        except OSError:
            slot_age = STALE_CODEX_SLOT_SECONDS + 1

        owner_pid = None
        if owner_text:
            try:
                owner_pid = int(owner_text.split("-", 1)[0])
            except ValueError:
                owner_pid = None

        owner_is_dead = owner_pid is not None and not is_process_alive(owner_pid)
        slot_is_old = slot_age > STALE_CODEX_SLOT_SECONDS
        if owner_is_dead or slot_is_old:
            shutil.rmtree(slot_path, ignore_errors=True)


def terminate_process_tree(process: subprocess.Popen | None) -> None:
    if not process or process.poll() is not None:
        return

    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            try:
                process.wait(timeout=5)
                return
            except subprocess.TimeoutExpired:
                pass
        else:
            process.terminate()
            try:
                process.wait(timeout=5)
                return
            except subprocess.TimeoutExpired:
                pass
    except Exception:
        pass

    try:
        process.kill()
    except Exception:
        pass


def toml_key(key: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_-]+", key):
        return key
    return '"' + key.replace("\\", "\\\\").replace('"', '\\"') + '"'


def toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        entries = [
            f"{toml_key(str(item_key))} = {toml_value(item_value)}"
            for item_key, item_value in value.items()
            if item_value is not None
        ]
        return "{ " + ", ".join(entries) + " }"
    raise TypeError(f"Unsupported Codex config value: {type(value).__name__}")


def toml_inline_table(mapping: dict) -> str:
    entries = [
        f"{toml_key(str(key))} = {toml_value(value)}"
        for key, value in mapping.items()
        if value is not None
    ]
    return "{ " + ", ".join(entries) + " }"


def load_codex_config() -> dict:
    config_path = RUNTIME_CODEX_HOME / "config.toml"
    try:
        with config_path.open("rb") as config_file:
            loaded_config = tomllib.load(config_file)
        return loaded_config if isinstance(loaded_config, dict) else {}
    except FileNotFoundError:
        return {}
    except tomllib.TOMLDecodeError:
        return {}


def codex_mcp_auto_approval_args() -> list[str]:
    codex_config = load_codex_config()
    mcp_servers = codex_config.get("mcp_servers", {})
    server_config = mcp_servers.get(JIRA_MCP_SERVER) if isinstance(mcp_servers, dict) else None
    if not isinstance(server_config, dict):
        return []

    server_override = dict(server_config)
    server_override["default_tools_approval_mode"] = "approve"
    return [
        "-c",
        f"mcp_servers.{toml_key(JIRA_MCP_SERVER)}={toml_inline_table(server_override)}",
    ]


def codex_approval_args() -> list[str]:
    args: list[str] = []
    if CODEX_BYPASS_APPROVALS:
        args.append("--dangerously-bypass-approvals-and-sandbox")
    else:
        args.extend(["--ask-for-approval", "never"])

    if CODEX_AUTO_APPROVE_MCP_TOOLS:
        args.extend(codex_mcp_auto_approval_args())

    if CODEX_AUTO_APPROVE_APPS:
        args.extend(
            [
                "-c",
                "apps._default.enabled=true",
                "-c",
                "apps._default.open_world_enabled=true",
                "-c",
                "apps._default.destructive_enabled=true",
                "-c",
                'apps._default.default_tools_approval_mode="approve"',
                "-c",
                "apps._default.default_tools_enabled=true",
            ]
        )
        for app_id in CODEX_AUTO_APPROVE_APP_IDS:
            args.extend(
                [
                    "-c",
                    f"apps.{toml_key(app_id)}.enabled=true",
                    "-c",
                    f"apps.{toml_key(app_id)}.open_world_enabled=true",
                    "-c",
                    f"apps.{toml_key(app_id)}.destructive_enabled=true",
                    "-c",
                    f'apps.{toml_key(app_id)}.default_tools_approval_mode="approve"',
                    "-c",
                    f"apps.{toml_key(app_id)}.default_tools_enabled=true",
                ]
            )

    return args


def build_codex_env() -> dict[str, str]:
    runtime_codex_home = ensure_runtime_codex_home()
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["CODEX_HOME"] = str(runtime_codex_home)
    env["NO_COLOR"] = "1"
    return env


def create_output_file() -> str:
    temp_dir = CODEX_SCRATCH_DIR / "tmp"
    output_file_descriptor, output_file_path = tempfile.mkstemp(
        prefix="codex-rca-output-",
        suffix=".txt",
        dir=str(temp_dir),
        text=True,
    )
    os.close(output_file_descriptor)
    return output_file_path


def build_codex_exec_command(output_file_path: str) -> list[str]:
    return [
        resolve_codex_path(),
        "exec",
        "--ephemeral",
        "--skip-git-repo-check",
        *codex_approval_args(),
        "-c",
        "shell_environment_policy.inherit=all",
        "--color",
        "never",
        "--output-last-message",
        output_file_path,
    ]


def read_codex_output(output_file_path: str) -> str:
    output = Path(output_file_path).read_text(encoding="utf-8").strip()
    if not output:
        raise RuntimeError("Codex CLI returned an empty response.")

    return strip_code_fences(output)


def run_codex(prompt: str, code_base_path: str | None = None) -> str:
    output_file_path = create_output_file()
    slot_path: Path | None = None
    process: subprocess.Popen | None = None

    try:
        code_base_dir = resolve_rca_code_base_dir(code_base_path)
        slot_path = acquire_codex_slot()
        process = subprocess.Popen(
            build_codex_exec_command(output_file_path),
            cwd=str(code_base_dir),
            env=build_codex_env(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        try:
            stdout, stderr = process.communicate(input=prompt, timeout=CODEX_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            terminate_process_tree(process)
            raise

        if stdout.strip():
            print(f"Codex CLI stdout:\n{stdout}", flush=True)
        if stderr.strip():
            print(f"Codex CLI stderr:\n{stderr}", flush=True)

        if process.returncode != 0:
            raise RuntimeError(
                "Codex CLI failed.\n"
                f"STDOUT:\n{stdout}\n\n"
                f"STDERR:\n{stderr}"
            )

        return read_codex_output(output_file_path)
    finally:
        terminate_process_tree(process)
        Path(output_file_path).unlink(missing_ok=True)
        release_codex_slot(slot_path)


async def run_codex_async(prompt: str, code_base_path: str | None = None) -> str:
    async with codex_job_semaphore:
        return await asyncio.to_thread(run_codex, prompt, code_base_path)


def append_rca_job_log(job_id: str, line: str) -> None:
    clean_line = line.rstrip()
    if not clean_line:
        return

    with rca_jobs_lock:
        job = rca_jobs.get(job_id)
        if not job:
            return
        job["logs"].append(clean_line)
        job["logs"] = job["logs"][-MAX_RCA_JOB_LOG_LINES:]


def update_rca_job(job_id: str, **updates) -> None:
    with rca_jobs_lock:
        job = rca_jobs.get(job_id)
        if not job:
            return
        if job.get("status") == "cancelled" and updates.get("status") not in (None, "cancelled"):
            return
        job.update(updates)


def serialize_rca_job(job: dict) -> dict:
    return {
        "job_id": job["job_id"],
        "jira_key": job["jira_key"],
        "code_base_path": job.get("code_base_path", str(CODE_BASE_DIR)),
        "status": job["status"],
        "logs": list(job["logs"]),
        "result": job["result"],
        "error": job["error"],
        "started_at": job["started_at"],
    }


def is_rca_job_cancelled(job_id: str) -> bool:
    with rca_jobs_lock:
        job = rca_jobs.get(job_id)
        return bool(job and job.get("cancel_requested"))


def register_rca_job_process(job_id: str, process: subprocess.Popen) -> bool:
    with rca_jobs_lock:
        job = rca_jobs.get(job_id)
        if not job:
            return False
        job["process"] = process
        return not job.get("cancel_requested")


def clear_rca_job_process(job_id: str, process: subprocess.Popen | None) -> None:
    with rca_jobs_lock:
        job = rca_jobs.get(job_id)
        if job and job.get("process") is process:
            job["process"] = None


def cancel_rca_job(job_id: str) -> dict:
    process: subprocess.Popen | None = None
    with rca_jobs_lock:
        job = rca_jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="RCA job not found.")
        if job["status"] in TERMINAL_RCA_STATUSES:
            return serialize_rca_job(job)

        job["cancel_requested"] = True
        job["status"] = "cancelled"
        job["error"] = "RCA job cancelled by user."
        job["result"] = None
        job["logs"].append("RCA job cancelled by user.")
        job["logs"] = job["logs"][-MAX_RCA_JOB_LOG_LINES:]
        process = job.get("process")

    terminate_process_tree(process)
    return get_rca_job(job_id)


def read_process_output(job_id: str, process: subprocess.Popen) -> None:
    if not process.stdout:
        return

    for line in process.stdout:
        append_rca_job_log(job_id, line)


def run_codex_for_rca_job(job_id: str, prompt: str, user_id: str = LOCAL_USER_ID, priority: str | None = None, code_base_path: str | None = None) -> None:
    output_file_path = create_output_file()
    slot_path: Path | None = None
    start = perf_counter()
    process: subprocess.Popen | None = None

    try:
        code_base_dir = validate_rca_paths(code_base_path)
        if is_rca_job_cancelled(job_id):
            return
        update_rca_job(job_id, status="running", started_at=time.time())
        append_rca_job_log(job_id, "Starting Codex CLI RCA process.")
        append_rca_job_log(job_id, f"Codebase: {code_base_dir}")
        append_rca_job_log(job_id, f"Memory-bank: {MEMORY_BANK_DIR}")
        append_rca_job_log(job_id, f"Skill: {RCA_SKILL_FILE}")
        append_rca_job_log(job_id, f"MCP server: {JIRA_MCP_SERVER}")

        slot_path = acquire_codex_slot(lambda: is_rca_job_cancelled(job_id))
        if is_rca_job_cancelled(job_id):
            return
        append_rca_job_log(job_id, "Codex execution slot acquired.")

        process = subprocess.Popen(
            build_codex_exec_command(output_file_path),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            cwd=str(code_base_dir),
            env=build_codex_env(),
            bufsize=1,
        )
        if not register_rca_job_process(job_id, process):
            terminate_process_tree(process)
            return

        if process.stdin:
            process.stdin.write(prompt)
            process.stdin.close()

        reader = threading.Thread(target=read_process_output, args=(job_id, process), daemon=True)
        reader.start()

        try:
            return_code = process.wait(timeout=CODEX_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            terminate_process_tree(process)
            append_rca_job_log(job_id, f"Codex CLI timed out after {CODEX_TIMEOUT_SECONDS} seconds.")
            update_rca_job(job_id, status="failed", error="Codex CLI timed out while processing the Jira RCA.")
            return

        reader.join(timeout=2)

        if is_rca_job_cancelled(job_id):
            return

        if return_code != 0:
            append_rca_job_log(job_id, f"Codex CLI exited with code {return_code}.")
            update_rca_job(job_id, status="failed", error=f"Codex CLI failed with exit code {return_code}.")
            return

        streamed_output = extract_streamed_rca_output(get_rca_job_logs(job_id))
        try:
            output = read_codex_output(output_file_path)
        except Exception:
            output = streamed_output

        if streamed_output and not looks_like_rca_output(output):
            output = streamed_output

        if not output:
            update_rca_job(job_id, status="failed", error="Codex CLI returned an empty RCA response.")
            return

        if looks_like_mcp_auth_cancelled(output):
            append_rca_job_log(job_id, "Jira MCP authentication is required before RCA can continue.")
            update_rca_job(job_id, status="auth_required", error="Jira MCP authentication is required.")
            return

        append_rca_job_log(job_id, "Codex RCA process completed.")
        tshirt_sizing = build_jira_tshirt_sizing(
            get_rca_job(job_id)["jira_key"],
            output,
            user_id=user_id,
            priority=priority,
        )
        update_rca_job(
            job_id,
            status="completed",
            result={
                "root_cause_analysis": output,
                "jira_tshirt_sizing": tshirt_sizing,
                "elapsed_seconds": perf_counter() - start,
            },
        )
    except RcaJobCancelled:
        return
    except Exception as exc:
        append_rca_job_log(job_id, f"RCA process failed: {exc}")
        update_rca_job(job_id, status="failed", error=str(exc))
    finally:
        terminate_process_tree(process)
        clear_rca_job_process(job_id, process)
        Path(output_file_path).unlink(missing_ok=True)
        release_codex_slot(slot_path)


def start_rca_job(jira_key: str, additional_context: str = "", user_id: str = LOCAL_USER_ID, priority: str | None = None, code_base_path: str | None = None) -> dict:
    normalized_jira_key = normalize_jira_key(jira_key)
    code_base_dir = validate_rca_paths(code_base_path)
    with rca_jobs_lock:
        for job in rca_jobs.values():
            if (
                job["jira_key"] == normalized_jira_key
                and job.get("code_base_path") == str(code_base_dir)
                and job["status"] in ACTIVE_RCA_STATUSES
            ):
                return serialize_rca_job(job)

    prompt = build_jira_rca_prompt(normalized_jira_key, additional_context, str(code_base_dir))
    job_id = uuid.uuid4().hex

    with rca_jobs_lock:
        rca_jobs[job_id] = {
            "job_id": job_id,
            "jira_key": normalized_jira_key,
            "code_base_path": str(code_base_dir),
            "status": "queued",
            "logs": ["Queued Jira RCA job."],
            "result": None,
            "error": "",
            "started_at": None,
            "cancel_requested": False,
            "process": None,
        }

    thread = threading.Thread(target=run_codex_for_rca_job, args=(job_id, prompt, user_id, priority, str(code_base_dir)), daemon=True)
    thread.start()
    return get_rca_job(job_id)


def get_rca_job(job_id: str) -> dict:
    with rca_jobs_lock:
        job = rca_jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="RCA job not found.")
        return serialize_rca_job(job)


def build_jira_sso_prompt(jira_key: str) -> str:
    return (
        f"Use the central_jira_confluence MCP server to fetch Jira {jira_key}. "
        "If a browser or SSO window opens, wait for me to complete authentication. "
        "After authentication succeeds, show the Jira summary and tell me I can retry Generate by AI in DevQuest."
    )


def start_jira_sso_session(jira_key: str) -> subprocess.Popen:
    ensure_runtime_codex_home()
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["CODEX_HOME"] = str(RUNTIME_CODEX_HOME)
    env["NO_COLOR"] = "1"

    command = [
        resolve_codex_path(),
        *codex_approval_args(),
        "-C",
        str(CODE_BASE_DIR),
        "-c",
        "shell_environment_policy.inherit=all",
        build_jira_sso_prompt(jira_key),
    ]

    creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    return subprocess.Popen(command, cwd=str(CODE_BASE_DIR), env=env, creationflags=creationflags)


def get_health_details() -> dict[str, str]:
    validate_rca_paths()
    ensure_runtime_codex_home()
    return {
        "status": "ok",
        "service": "jira-rca",
        "codex_cli": Path(resolve_codex_path()).name,
        "codex_home": str(RUNTIME_CODEX_HOME),
        "codex_scratch_dir": str(CODEX_SCRATCH_DIR),
        "code_base_dir": str(CODE_BASE_DIR),
        "memory_bank_dir": str(MEMORY_BANK_DIR),
        "rca_skill_file": str(RCA_SKILL_FILE),
        "jira_mcp_server": JIRA_MCP_SERVER,
        "codex_auto_approve_mcp_tools": str(CODEX_AUTO_APPROVE_MCP_TOOLS).lower(),
        "codex_auto_approve_apps": str(CODEX_AUTO_APPROVE_APPS).lower(),
        "max_concurrent_codex_jobs": str(MAX_CONCURRENT_CODEX_JOBS),
    }
