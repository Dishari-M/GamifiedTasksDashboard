import copy
import json
import os
from datetime import datetime, timezone
from threading import Lock


DEFAULT_CACHE_TTL_SECONDS = 300
_CACHE = {}
_CACHE_LOCK = Lock()


def canonical_cache_key(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def get_default_cache_ttl_seconds():
    value = os.getenv("DEVQUEST_API_CACHE_TTL_SECONDS")
    if value in (None, ""):
        return DEFAULT_CACHE_TTL_SECONDS
    try:
        ttl = int(value)
    except ValueError:
        return DEFAULT_CACHE_TTL_SECONDS
    return max(0, ttl)


def get_cached_response(namespace, key, ttl_seconds):
    now = _now()
    with _CACHE_LOCK:
        entry = _CACHE.get((namespace, key))
        if not entry:
            return None
        if now - entry["cached_at"] > ttl_seconds:
            _CACHE.pop((namespace, key), None)
            return None
        return copy.deepcopy(entry["value"])


def set_cached_response(namespace, key, value, user_id=None):
    with _CACHE_LOCK:
        _CACHE[(namespace, key)] = {
            "cached_at": _now(),
            "user_id": user_id,
            "value": copy.deepcopy(value),
        }


def invalidate_namespace(namespace, user_id=None):
    with _CACHE_LOCK:
        for cache_key, entry in list(_CACHE.items()):
            if cache_key[0] != namespace:
                continue
            if user_id is not None and entry.get("user_id") != user_id:
                continue
            _CACHE.pop(cache_key, None)


def invalidate_user_cache(user_id, namespaces=None):
    namespace_filter = set(namespaces or [])
    with _CACHE_LOCK:
        for cache_key, entry in list(_CACHE.items()):
            if namespace_filter and cache_key[0] not in namespace_filter:
                continue
            if entry.get("user_id") == user_id:
                _CACHE.pop(cache_key, None)


def get_cache_stats():
    with _CACHE_LOCK:
        return {
            "entries": len(_CACHE),
            "namespaces": sorted({key[0] for key in _CACHE}),
        }


def _now():
    return datetime.now(timezone.utc).timestamp()
