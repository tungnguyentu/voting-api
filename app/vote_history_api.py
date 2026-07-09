import json
from typing import Any

from fastapi import HTTPException

from app.config import HISTORY_ATTENDANCE_KEY, HISTORY_VOTE_KEY


def load_vote_history(redis_client: Any, redis_key: str = HISTORY_VOTE_KEY) -> list[dict[str, Any]]:
    payload = redis_client.get(redis_key)
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail=f"Redis key '{redis_key}' was not found.",
        )

    return json.loads(payload)


def load_attendance_history(redis_client: Any, redis_key: str = HISTORY_ATTENDANCE_KEY) -> list[dict[str, Any]]:
    payload = redis_client.get(redis_key)
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail=f"Redis key '{redis_key}' was not found.",
        )

    return json.loads(payload)
