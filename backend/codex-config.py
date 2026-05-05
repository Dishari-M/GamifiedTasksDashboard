from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
from time import perf_counter

from fastapi import HTTPException


SERVICE_DIR = Path(__file__).resolve().parent
DEFAULT_CODEX_HOME = Path.home() / ".codex"
RUNTIME_CODEX_HOME = Path(os.getenv("JIRA_RCA_CODEX_HOME", str(DEFAULT_CODEX_HOME)))
CODEX_SCRATCH_DIR = SERVICE_DIR / ".codex-rca-runtime"

CODE_BASE_DIR = Path(os.getenv("RCA_CODE_BASE_DIR", r"C:\Oracle_Repo"))
MEMORY_BANK_DIR = Path(os.getenv("RCA_MEMORY_BANK_DIR", str(CODE_BASE_DIR / "memory-bank")))
RCA_SKILL_DIR = Path(os.getenv("RCA_SKILL_DIR", str(CODE_BASE_DIR / ".agents" / "skills" / "enterprise-rca")))
RCA_SKILL_FILE = RCA_SKILL_DIR / "SKILL.md"
JIRA_MCP_SERVER = os.getenv("JIRA_MCP_SERVER", "central_jira_confluence")

CODEX_TIMEOUT_SECONDS = max(1, int(os.getenv("CODEX_TIMEOUT_SECONDS", "900")))
CODEX_BYPASS_APPROVALS = os.getenv("CODEX_BYPASS_APPROVALS", "true").strip().lower() not in ("0", "false", "no")
MAX_CONCURRENT_CODEX_JOBS = max(1, int(os.getenv("MAX_CONCURRENT_CODEX_JOBS", "2")))
CODEX_QUEUE_TIMEOUT_SECONDS = max(1, int(os.getenv("CODEX_QUEUE_TIMEOUT_SECONDS", "30")))
CODEX_SLOT_POLL_INTERVAL_SECONDS = 0.2
MAX_RCA_JOB_LOG_LINES = max(500, int(os.getenv("MAX_RCA_JOB_LOG_LINES", "5000")))
JIRA_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")

codex_job_semaphore = asyncio.Semaphore(MAX_CONCURRENT_CODEX_JOBS)
rca_jobs: dict[str, dict] = {}
rca_jobs_lock = threading.Lock()

JIRA_RCA_SYSTEM_PROMPT = """
You are an enterprise Jira root-cause-analysis agent.

MANDATORY SOURCES:
1. Fetch Jira details and Jira comments from MCP server: central_jira_confluence.
2. Use the enterprise RCA skill instructions from C:\\Oracle_Repo\\.agents\\skills\\enterprise-rca\\SKILL.md.
3. Use C:\\Oracle_Repo\\memory-bank as the primary architecture/context reference.
4. Analyze the codebase rooted at C:\\Oracle_Repo.

STRICT RULES:
1. Start from the Jira key. Fetch Jira summary, description, status, issue type, priority, components, labels, affects version, fix version, attachments/log snippets if visible, and comments.
2. If Jira includes Affects Version, use it to choose UI code locations according to the RCA skill.
3. Read memory-bank files before drawing conclusions.
4. Trace code flow through relevant modules and build.gradle dependencies. Do not stop at the first matching file.
5. Root cause must identify the specific failing condition in code or data flow, not just the symptom.
6. Cite exact local file paths for affected files and explain why each file matters.
7. If evidence is insufficient, say exactly what is missing and provide the best-supported hypothesis separately.
8. Do not modify files. This service is analysis-only.
9. Do not output markdown code fences around the whole response.

REPORTING:
Follow the enterprise RCA skill's required workflow and output format.
Do not add a separate one-line Jira description or task-form summary during RCA.
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


def validate_rca_paths() -> None:
    if not CODE_BASE_DIR.exists():
        raise RuntimeError(f"Code base directory not found: {CODE_BASE_DIR}")
    if not MEMORY_BANK_DIR.exists():
        raise RuntimeError(f"Memory-bank directory not found: {MEMORY_BANK_DIR}")
    if not RCA_SKILL_FILE.exists():
        raise RuntimeError(f"Enterprise RCA skill not found: {RCA_SKILL_FILE}")


def normalize_jira_key(jira_key: str) -> str:
    normalized = jira_key.strip().upper()
    if not JIRA_KEY_PATTERN.match(normalized):
        raise HTTPException(status_code=400, detail="jira_key must look like HEPRT-123")
    return normalized


def build_jira_rca_prompt(jira_key: str, additional_context: str = "") -> str:
    validate_rca_paths()
    rca_skill = load_text(RCA_SKILL_FILE)
    context_block = additional_context.strip() or "N/A"

    return f"""
{JIRA_RCA_SYSTEM_PROMPT}

===== RUNTIME CONFIG =====
Jira MCP server: {JIRA_MCP_SERVER}
Code base path: {CODE_BASE_DIR}
Memory-bank path: {MEMORY_BANK_DIR}
Enterprise RCA skill path: {RCA_SKILL_FILE}

===== ENTERPRISE RCA SKILL =====
{rca_skill}

===== JIRA REQUEST =====
Jira key: {jira_key}

===== ADDITIONAL CONTEXT =====
{context_block}

Now fetch the Jira details and comments using the {JIRA_MCP_SERVER} MCP server, analyze the codebase at {CODE_BASE_DIR}, and produce the requested output format.
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


def acquire_codex_slot() -> Path:
    ensure_runtime_codex_home()
    locks_dir = CODEX_SCRATCH_DIR / "locks"
    deadline = perf_counter() + CODEX_QUEUE_TIMEOUT_SECONDS
    owner_token = f"{os.getpid()}-{uuid.uuid4().hex}"

    while perf_counter() < deadline:
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


def codex_approval_args() -> list[str]:
    if CODEX_BYPASS_APPROVALS:
        return ["--dangerously-bypass-approvals-and-sandbox"]

    return [
        "-c",
        'approval_policy="never"',
    ]


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


def run_codex(prompt: str) -> str:
    output_file_path = create_output_file()
    slot_path: Path | None = None

    try:
        slot_path = acquire_codex_slot()
        result = subprocess.run(
            build_codex_exec_command(output_file_path),
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(CODE_BASE_DIR),
            env=build_codex_env(),
            timeout=CODEX_TIMEOUT_SECONDS,
        )

        if result.stdout.strip():
            print(f"Codex CLI stdout:\n{result.stdout}", flush=True)
        if result.stderr.strip():
            print(f"Codex CLI stderr:\n{result.stderr}", flush=True)

        if result.returncode != 0:
            raise RuntimeError(
                "Codex CLI failed.\n"
                f"STDOUT:\n{result.stdout}\n\n"
                f"STDERR:\n{result.stderr}"
            )

        return read_codex_output(output_file_path)
    finally:
        Path(output_file_path).unlink(missing_ok=True)
        release_codex_slot(slot_path)


async def run_codex_async(prompt: str) -> str:
    async with codex_job_semaphore:
        return await asyncio.to_thread(run_codex, prompt)


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
        if job_id in rca_jobs:
            rca_jobs[job_id].update(updates)


def read_process_output(job_id: str, process: subprocess.Popen) -> None:
    if not process.stdout:
        return

    for line in process.stdout:
        append_rca_job_log(job_id, line)


def run_codex_for_rca_job(job_id: str, prompt: str) -> None:
    output_file_path = create_output_file()
    slot_path: Path | None = None
    start = perf_counter()
    process: subprocess.Popen | None = None

    try:
        update_rca_job(job_id, status="running", started_at=time.time())
        append_rca_job_log(job_id, "Starting Codex CLI RCA process.")
        append_rca_job_log(job_id, f"Codebase: {CODE_BASE_DIR}")
        append_rca_job_log(job_id, f"Memory-bank: {MEMORY_BANK_DIR}")
        append_rca_job_log(job_id, f"Skill: {RCA_SKILL_FILE}")
        append_rca_job_log(job_id, f"MCP server: {JIRA_MCP_SERVER}")

        slot_path = acquire_codex_slot()
        append_rca_job_log(job_id, "Codex execution slot acquired.")

        process = subprocess.Popen(
            build_codex_exec_command(output_file_path),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            cwd=str(CODE_BASE_DIR),
            env=build_codex_env(),
            bufsize=1,
        )

        if process.stdin:
            process.stdin.write(prompt)
            process.stdin.close()

        reader = threading.Thread(target=read_process_output, args=(job_id, process), daemon=True)
        reader.start()

        try:
            return_code = process.wait(timeout=CODEX_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            append_rca_job_log(job_id, f"Codex CLI timed out after {CODEX_TIMEOUT_SECONDS} seconds.")
            update_rca_job(job_id, status="failed", error="Codex CLI timed out while processing the Jira RCA.")
            return

        reader.join(timeout=2)

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
        update_rca_job(
            job_id,
            status="completed",
            result={
                "root_cause_analysis": output,
                "elapsed_seconds": perf_counter() - start,
            },
        )
    except Exception as exc:
        append_rca_job_log(job_id, f"RCA process failed: {exc}")
        update_rca_job(job_id, status="failed", error=str(exc))
    finally:
        if process and process.poll() is None:
            process.kill()
        Path(output_file_path).unlink(missing_ok=True)
        release_codex_slot(slot_path)


def start_rca_job(jira_key: str, additional_context: str = "") -> dict:
    normalized_jira_key = normalize_jira_key(jira_key)
    prompt = build_jira_rca_prompt(normalized_jira_key, additional_context)
    job_id = uuid.uuid4().hex

    with rca_jobs_lock:
        rca_jobs[job_id] = {
            "job_id": job_id,
            "jira_key": normalized_jira_key,
            "status": "queued",
            "logs": ["Queued Jira RCA job."],
            "result": None,
            "error": "",
            "started_at": None,
        }

    thread = threading.Thread(target=run_codex_for_rca_job, args=(job_id, prompt), daemon=True)
    thread.start()
    return get_rca_job(job_id)


def get_rca_job(job_id: str) -> dict:
    with rca_jobs_lock:
        job = rca_jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="RCA job not found.")
        return {
            "job_id": job["job_id"],
            "jira_key": job["jira_key"],
            "status": job["status"],
            "logs": list(job["logs"]),
            "result": job["result"],
            "error": job["error"],
            "started_at": job["started_at"],
        }


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
        "max_concurrent_codex_jobs": str(MAX_CONCURRENT_CODEX_JOBS),
    }
