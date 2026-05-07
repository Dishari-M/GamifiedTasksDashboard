import os
from contextlib import contextmanager
from threading import Lock

import oracledb


DEFAULT_POOL_SIZE = 1

_POOL = None
_POOL_LOCK = Lock()
_THICK_MODE_READY = False


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _maybe_init_thick_mode(wallet_dir):
    global _THICK_MODE_READY

    if _THICK_MODE_READY or not _truthy(os.getenv("ORACLE_DB_THICK_MODE")):
        return

    client_dir = os.getenv("ORACLE_CLIENT_LIB_DIR", "").strip()
    init_kwargs = {}
    if client_dir:
        init_kwargs["lib_dir"] = client_dir
    if wallet_dir:
        init_kwargs["config_dir"] = wallet_dir

    oracledb.init_oracle_client(**init_kwargs)
    _THICK_MODE_READY = True


def _connection_args():
    wallet_dir = os.getenv("DB_WALLET_DIR", "").strip()
    _maybe_init_thick_mode(wallet_dir)

    args = {
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "dsn": os.getenv("DB_DSN"),
    }

    if wallet_dir:
        args["config_dir"] = wallet_dir
        args["wallet_location"] = wallet_dir
        wallet_password = os.getenv("DB_WALLET_PASSWORD", "").strip()
        if wallet_password:
            args["wallet_password"] = wallet_password
    return args


def _env_int(name, default):
    value = os.getenv(name)
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if parsed < 0:
        raise ValueError(f"{name} must be zero or greater.")
    return parsed


def _pool_config():
    """Return Oracle pool sizing.

    Oracle's python-oracledb guidance recommends fixed-size pools to avoid
    connection storms, so DB_POOL_SIZE drives both min and max by default.
    DB_POOL_MIN / DB_POOL_MAX remain available when a deployment has a
    deliberate reason to use a non-fixed pool.
    """
    pool_size = _env_int("DB_POOL_SIZE", DEFAULT_POOL_SIZE)
    pool_min = _env_int("DB_POOL_MIN", pool_size)
    pool_max = _env_int("DB_POOL_MAX", pool_size)
    if pool_min > pool_max:
        raise ValueError("DB_POOL_MIN cannot be greater than DB_POOL_MAX.")
    return {
        "min": pool_min,
        "max": pool_max,
        "increment": _env_int("DB_POOL_INCREMENT", 1),
        "timeout": _env_int("DB_POOL_TIMEOUT", 0),
    }


def init_pool():
    global _POOL
    if _POOL is not None:
        return _POOL
    with _POOL_LOCK:
        if _POOL is None:
            _POOL = oracledb.create_pool(
                **_connection_args(),
                **_pool_config(),
            )
    return _POOL


def get_connection():
    """Acquire a pooled Oracle connection.

    Prefer `connection_scope()` for request-path code so the connection is
    always returned to the pool. If this lower-level helper is used directly,
    the caller must close the connection in a finally block.

    Do not call oracledb.connect() directly in request paths because ADB wallet
    connection setup is expensive and causes slow API responses.
    """
    return init_pool().acquire()


@contextmanager
def connection_scope():
    """Yield a pooled connection and always return it to the pool.

    Use this for API request paths:

        with connection_scope() as conn:
            ...

    Closing a pooled connection returns it to the pool; it does not close the
    physical database session unless the pool decides to shrink or drop it.
    """
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def close_pool():
    """Close the process-local pool, mainly for tests or app shutdown hooks."""
    global _POOL
    with _POOL_LOCK:
        if _POOL is not None:
            _POOL.close()
            _POOL = None


def get_pool_stats():
    pool = init_pool()
    return {
        "opened": pool.opened,
        "busy": pool.busy,
        "idle": pool.opened - pool.busy,
        **_pool_config(),
    }
