from typing import Any, Optional

from fastapi import FastAPI

from app.config import HISTORY_REDIS_URL
from app.redis_client import create_redis_client
from app.vote_history_api import load_attendance_history, load_vote_history


def create_app(history_redis_client: Optional[Any] = None) -> FastAPI:
    app = FastAPI()

    app.state.history_redis_client = history_redis_client or create_redis_client(
        HISTORY_REDIS_URL,
    )

    @app.get("/history/vote")
    def get_vote_history() -> list[dict[str, Any]]:
        return load_vote_history(app.state.history_redis_client)

    @app.get("/history/attendance")
    def get_attendance_history() -> list[dict[str, Any]]:
        return load_attendance_history(app.state.history_redis_client)

    return app


app = create_app()
