import threading
import time
from pathlib import Path


LOG_DIR = Path(__file__).resolve().parents[1] / ".sync-logs"
MAX_LOG_BYTES = 750_000
TRIM_TO_BYTES = 500_000
_LOCK = threading.Lock()


def append_log(sync_run_id, message, level="INFO"):
    append_logs(sync_run_id, [message], level)


def append_logs(sync_run_id, messages, level="INFO"):
    rows = [str(message or "").strip() for message in messages or [] if str(message or "").strip()]
    if not rows:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = _write_path(sync_run_id)
    with _LOCK:
        _trim_if_needed(path)
        with path.open("a", encoding="utf-8") as handle:
            for message in rows:
                handle.write(_format_line(message, level) + "\n")


def _write_path(sync_run_id):
    return LOG_DIR / f"sync-run-{int(sync_run_id)}.txt"


def _format_line(message, level):
    timestamp = int(time.time() * 1000)
    level_code = _level_code(level)
    compact_message = str(message or "").replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    return f"{timestamp}|{level_code}|{compact_message}"


def _level_code(level):
    normalized = str(level or "INFO").upper()
    if normalized.startswith("ERR"):
        return "E"
    if normalized.startswith("WARN"):
        return "W"
    return "I"


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
