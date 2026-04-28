"""
Simple in-memory TTL cache for read-heavy, slowly-changing endpoints.

Stock prices update every 15 minutes via the Azure job, so caching
API responses for 10 minutes eliminates redundant DB window-function
queries across concurrent users.
"""
import time
from typing import Any, Optional

_store: dict[str, tuple[Any, float]] = {}


def get(key: str, ttl: int) -> Optional[Any]:
    entry = _store.get(key)
    if entry is None:
        return None
    value, ts = entry
    if time.time() - ts > ttl:
        del _store[key]
        return None
    return value


def set(key: str, value: Any) -> None:
    _store[key] = (value, time.time())


def invalidate(key: str) -> None:
    _store.pop(key, None)
