import json
import os
import tempfile
import threading
from pathlib import Path


_LOCK = threading.Lock()
_DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def data_dir():
    return Path(os.getenv("DEVQUEST_DATA_DIR", _DEFAULT_DATA_DIR))


def read_records(name):
    path = data_dir() / name
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_records(name, records):
    directory = data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    fd, temp_name = tempfile.mkstemp(prefix=f".{name}.", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(records, handle, indent=2)
            handle.write("\n")
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def with_store_lock(action):
    with _LOCK:
        return action()
