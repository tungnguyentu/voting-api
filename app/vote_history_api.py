import json
from typing import Any

from app.config import HISTORY_ATTENDANCE_KEY, HISTORY_DISCUSS_KEY, HISTORY_VOTE_KEY


def _load_history_list(redis_client: Any, redis_key: str) -> list[dict[str, Any]]:
    payload = redis_client.get(redis_key)
    if payload is None:
        # No history yet (e.g. before first Start, or after Clear) → empty list
        return []

    data = json.loads(payload)
    if not isinstance(data, list):
        return []
    return data


def load_vote_history(redis_client: Any, redis_key: str = HISTORY_VOTE_KEY) -> list[dict[str, Any]]:
    return _load_history_list(redis_client, redis_key)


def load_attendance_history(redis_client: Any, redis_key: str = HISTORY_ATTENDANCE_KEY) -> list[dict[str, Any]]:
    return _load_history_list(redis_client, redis_key)


def load_discuss_history(redis_client: Any, redis_key: str = HISTORY_DISCUSS_KEY) -> list[dict[str, Any]]:
    return _load_history_list(redis_client, redis_key)
