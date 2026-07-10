import json

import fakeredis
from fastapi.testclient import TestClient

from app.main import create_app


def test_vote_history_returns_grouped_results_from_history_redis() -> None:
    history_redis = fakeredis.FakeStrictRedis(decode_responses=True)
    history_redis.set(
        "vote_history",
        json.dumps(
            [
                {
                    "vote_index": 1,
                    "started_at": "2026-07-09T11:15:03+07:00",
                    "ended_at": "2026-07-09T11:16:22+07:00",
                    "duration_seconds": 79,
                    "items": [
                        {
                            "delegate_id": 1103,
                            "delegate_name": "Bui Tuan Anh",
                            "delegate_address": "12 Tran Hung Dao, Ha Noi",
                            "delegate_group_name": "06. Don Vi Bau Cu So 6",
                            "delegate_street": "12 Tran Hung Dao",
                            "delegate_street_number": "",
                            "delegate_city": "Ha Noi",
                            "result": "Tan thanh",
                        }
                    ],
                }
            ]
        ),
    )
    client = TestClient(create_app(history_redis_client=history_redis))

    response = client.get("/history/vote")

    assert response.status_code == 200
    assert response.json() == [
        {
            "vote_index": 1,
            "started_at": "2026-07-09T11:15:03+07:00",
            "ended_at": "2026-07-09T11:16:22+07:00",
            "duration_seconds": 79,
            "items": [
                {
                    "delegate_id": 1103,
                    "delegate_name": "Bui Tuan Anh",
                    "delegate_address": "12 Tran Hung Dao, Ha Noi",
                    "delegate_group_name": "06. Don Vi Bau Cu So 6",
                    "delegate_street": "12 Tran Hung Dao",
                    "delegate_street_number": "",
                    "delegate_city": "Ha Noi",
                    "result": "Tan thanh",
                }
            ],
        }
    ]


def test_vote_history_returns_not_found_when_history_redis_key_is_missing() -> None:
    history_redis = fakeredis.FakeStrictRedis(decode_responses=True)
    client = TestClient(create_app(history_redis_client=history_redis))

    response = client.get("/history/vote")

    assert response.status_code == 404
    assert response.json() == {"detail": "Redis key 'vote_history' was not found."}


def test_attendance_history_returns_grouped_results_from_history_redis() -> None:
    history_redis = fakeredis.FakeStrictRedis(decode_responses=True)
    history_redis.set(
        "attendance_history",
        json.dumps(
            [
                {
                    "attendance_index": 1,
                    "started_at": "2026-07-09T10:15:03+07:00",
                    "ended_at": "2026-07-09T10:16:22+07:00",
                    "duration_seconds": 79,
                    "present": [
                        {
                            "delegate_id": 1200,
                            "delegate_name": "Nguyen Duy Chinh",
                            "delegate_address": "",
                            "delegate_group_name": "10. Don Vi Bau Cu So 10",
                            "delegate_street": "",
                            "delegate_street_number": "",
                            "delegate_city": "",
                            "result": "diemdanh",
                        }
                    ],
                    "missing": [
                        {
                            "delegate_id": 1103,
                            "delegate_name": "Bui Tuan Anh",
                            "delegate_address": "12 Tran Hung Dao, Ha Noi",
                            "delegate_group_name": "06. Don Vi Bau Cu So 6",
                            "delegate_street": "12 Tran Hung Dao",
                            "delegate_street_number": "",
                            "delegate_city": "Ha Noi",
                        }
                    ],
                }
            ]
        ),
    )
    client = TestClient(create_app(history_redis_client=history_redis))

    response = client.get("/history/attendance")

    assert response.status_code == 200
    assert response.json() == [
        {
            "attendance_index": 1,
            "started_at": "2026-07-09T10:15:03+07:00",
            "ended_at": "2026-07-09T10:16:22+07:00",
            "duration_seconds": 79,
            "present": [
                {
                    "delegate_id": 1200,
                    "delegate_name": "Nguyen Duy Chinh",
                    "delegate_address": "",
                    "delegate_group_name": "10. Don Vi Bau Cu So 10",
                    "delegate_street": "",
                    "delegate_street_number": "",
                    "delegate_city": "",
                    "result": "diemdanh",
                }
            ],
            "missing": [
                {
                    "delegate_id": 1103,
                    "delegate_name": "Bui Tuan Anh",
                    "delegate_address": "12 Tran Hung Dao, Ha Noi",
                    "delegate_group_name": "06. Don Vi Bau Cu So 6",
                    "delegate_street": "12 Tran Hung Dao",
                    "delegate_street_number": "",
                    "delegate_city": "Ha Noi",
                }
            ],
        }
    ]


def test_attendance_history_returns_not_found_when_history_redis_key_is_missing() -> None:
    history_redis = fakeredis.FakeStrictRedis(decode_responses=True)
    client = TestClient(create_app(history_redis_client=history_redis))

    response = client.get("/history/attendance")

    assert response.status_code == 404
    assert response.json() == {"detail": "Redis key 'attendance_history' was not found."}


def test_discuss_history_returns_grouped_results_from_history_redis() -> None:
    history_redis = fakeredis.FakeStrictRedis(decode_responses=True)
    history_redis.set(
        "discuss_history",
        json.dumps(
            [
                {
                    "discuss_index": 1,
                    "display": "DISCUSS",
                    "started_at": "2026-07-09T14:00:00+07:00",
                    "ended_at": "2026-07-09T14:10:00+07:00",
                    "duration_seconds": 600,
                    "waiting": [{"delegate_id": 1103, "display": "Bui Tuan Anh"}],
                    "talking": [{"delegate_id": 1200, "display": "Nguyen Duy Chinh"}],
                    "events": [
                        {
                            "at": "2026-07-09T14:01:00+07:00",
                            "state": "On",
                            "waiting": [],
                            "talking": [{"delegate_id": 1200, "display": "Nguyen Duy Chinh"}],
                        }
                    ],
                }
            ]
        ),
    )
    client = TestClient(create_app(history_redis_client=history_redis))

    response = client.get("/history/discuss")

    assert response.status_code == 200
    assert response.json() == [
        {
            "discuss_index": 1,
            "display": "DISCUSS",
            "started_at": "2026-07-09T14:00:00+07:00",
            "ended_at": "2026-07-09T14:10:00+07:00",
            "duration_seconds": 600,
            "waiting": [{"delegate_id": 1103, "display": "Bui Tuan Anh"}],
            "talking": [{"delegate_id": 1200, "display": "Nguyen Duy Chinh"}],
            "events": [
                {
                    "at": "2026-07-09T14:01:00+07:00",
                    "state": "On",
                    "waiting": [],
                    "talking": [{"delegate_id": 1200, "display": "Nguyen Duy Chinh"}],
                }
            ],
        }
    ]


def test_discuss_history_returns_not_found_when_history_redis_key_is_missing() -> None:
    history_redis = fakeredis.FakeStrictRedis(decode_responses=True)
    client = TestClient(create_app(history_redis_client=history_redis))

    response = client.get("/history/discuss")

    assert response.status_code == 404
    assert response.json() == {"detail": "Redis key 'discuss_history' was not found."}


def test_cors_allows_configured_origins() -> None:
    history_redis = fakeredis.FakeStrictRedis(decode_responses=True)
    client = TestClient(create_app(history_redis_client=history_redis))

    for origin in (
        "https://ihdnd.hanoi.gov.vn",
        "http://ihdnd.hanoi.gov.vn",
        "http://10.10.98.186",
        "https://10.10.98.186",
    ):
        response = client.options(
            "/history/vote",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
