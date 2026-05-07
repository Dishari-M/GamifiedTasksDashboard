import threading
import time
from datetime import datetime, timezone
from pathlib import Path


LOG_DIR = Path(__file__).resolve().parents[1] / ".enrichment-logs"
MAX_LOG_BYTES = 750_000
TRIM_TO_BYTES = 500_000
_LOCK = threading.Lock()


def append_log(user_id, job_id, message, level="INFO"):
    append_logs(user_id, job_id, [message], level)


def append_logs(user_id, job_id, messages, level="INFO"):
    rows = [str(message or "").strip() for message in messages or [] if str(message or "").strip()]
    if not rows:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = _write_path(job_id)
    with _LOCK:
        _trim_if_needed(path)
        handle = path.open("a", encoding="utf-8")
        try:
            for message in rows:
                handle.write(_format_line(message, level) + "\n")
        finally:
            handle.close()


def read_logs(job_id, limit=300):
    path = _log_path(job_id)
    if not path.exists():
        return []

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    selected = lines[-int(limit or 300) :]
    start_id = max(1, len(lines) - len(selected) + 1)
    logs = []
    for index, line in enumerate(selected, start=start_id):
        if not line.strip():
            continue
        logs.append(_parse_line(index, line))
    return logs


def _parse_line(log_id, line):
    timestamp, level, message = _parse_compact_line(line)
    if timestamp is not None:
        return {
            "log_id": log_id,
            "level": _level_name(level),
            "message": message,
            "created_at": _created_at(timestamp),
        }
    try:
        import json

        payload = json.loads(line)
        return {
            "log_id": log_id,
            "level": payload.get("level") or "INFO",
            "message": payload.get("message") or "",
            "created_at": payload.get("created_at") or "",
        }
    except (TypeError, ValueError):
        return {
            "log_id": log_id,
            "level": "INFO",
            "message": line,
            "created_at": "",
        }


def _log_path(job_id):
    path = LOG_DIR / f"job-{int(job_id)}.txt"
    legacy_path = LOG_DIR / f"job-{int(job_id)}.log"
    return path if path.exists() or not legacy_path.exists() else legacy_path


def _write_path(job_id):
    return LOG_DIR / f"job-{int(job_id)}.txt"


def _format_line(message, level):
    timestamp = int(time.time() * 1000)
    level_code = _level_code(level)
    compact_message = str(message or "").replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    return f"{timestamp}|{level_code}|{compact_message}"


def _parse_compact_line(line):
    parts = line.split("|", 2)
    if len(parts) != 3 or not parts[0].isdigit():
        return None, None, None
    return int(parts[0]), parts[1], parts[2]


def _level_code(level):
    normalized = str(level or "INFO").upper()
    if normalized.startswith("ERR"):
        return "E"
    if normalized.startswith("WARN"):
        return "W"
    return "I"


def _level_name(level_code):
    if level_code == "E":
        return "ERROR"
    if level_code == "W":
        return "WARN"
    return "INFO"


def _created_at(timestamp):
    try:
        return datetime.fromtimestamp(timestamp / 1000, timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return ""


def _trim_if_needed(path):
    try:
        if not path.exists() or path.stat().st_size <= MAX_LOG_BYTES:
            return
        data = path.read_bytes()[-TRIM_TO_BYTES:]
        first_newline = data.find(b"\n")
        if first_newline > -1:
            data = data[first_newline + 1 :]
        path.write_bytes(data)
    except OSError:
        return
