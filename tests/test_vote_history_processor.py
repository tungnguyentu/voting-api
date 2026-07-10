import json
import logging
from collections import deque

import fakeredis

from app.vote_history_listener import (
    VoteHistoryProcessor,
    listen_vote_history,
    process_pubsub_message,
)


def test_vote_history_processor_builds_history_with_vote_times_and_contact_fallback() -> None:
    source_redis = fakeredis.FakeStrictRedis(decode_responses=True)
    history_redis = fakeredis.FakeStrictRedis(decode_responses=True)
    source_redis.set(
        "voting_result",
        json.dumps(
            {
                "contact": {
                    "1103": {
                        "Id": 1103,
                        "Name": "Bui Tuan Anh",
                        "GroupName": "06. Don Vi Bau Cu So 6",
                        "Street": "12 Tran Hung Dao",
                        "StreetNumber": "",
                        "City": "Ha Noi",
                    },
                    "1104": {
                        "Id": 1104,
                        "Name": "Trinh Quang Anh",
                        "GroupName": "11. Don Vi Bau Cu So 11",
                        "Street": "",
                        "StreetNumber": "",
                        "City": "",
                    },
                },
                "contact_missing": [],
                "vote": {"ATTENDANCE": [{"1200": "diemdanh"}], "VOTE": []},
            }
        ),
    )
    processor = VoteHistoryProcessor(source_redis=source_redis, history_redis=history_redis)

    processor.handle_event(
        {
            "event_type": "SET_START",
            "payload": {"display": "VOTE"},
        },
        timestamp="2026-07-09T11:15:03+07:00",
    )
    processor.handle_event(
        {
            "event_type": "GENERAL_VOTING_RESULT",
            "payload": {
                "display": "VOTE",
                "meeting_voting_options": {
                    "VOTE": {
                        "1": {"Name": "Tan thanh"},
                        "2": {"Name": "Khong tan thanh"},
                    }
                },
                "voting_results": [
                    {"delegate_id": 1103, "voting_option_id": 1, "seat_number": "A1"},
                    {"delegate_id": 1104, "voting_option_id": 2, "seat_number": "A2"},
                ],
                "online": 2,
            },
        },
        timestamp="2026-07-09T11:15:20+07:00",
    )
    processor.handle_event(
        {
            "event_type": "SET_STOP",
            "payload": {"display": "VOTE"},
        },
        timestamp="2026-07-09T11:16:22+07:00",
    )

    stored_history = json.loads(history_redis.get("vote_history"))

    assert stored_history == [
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
                },
                {
                    "delegate_id": 1104,
                    "delegate_name": "Trinh Quang Anh",
                    "delegate_address": "",
                    "delegate_group_name": "11. Don Vi Bau Cu So 11",
                    "delegate_street": "",
                    "delegate_street_number": "",
                    "delegate_city": "",
                    "result": "Khong tan thanh",
                },
            ],
        }
    ]


def test_attendance_history_finalized_on_set_stop_with_present_and_missing() -> None:
    # Matches voting app: SET_STOP(ATTENDANCE) payload carries present_delegates + contact_missing.
    # Live GENERAL_VOTING_RESULT also publishes those lists (cached if needed).
    source_redis = fakeredis.FakeStrictRedis(decode_responses=True)
    history_redis = fakeredis.FakeStrictRedis(decode_responses=True)
    processor = VoteHistoryProcessor(source_redis=source_redis, history_redis=history_redis)

    present = {
        "1200": {
            "Id": 1200,
            "Name": "Nguyen Duy Chinh",
            "GroupName": "10. Don Vi Bau Cu So 10",
            "Street": "",
            "StreetNumber": "",
            "City": "",
        }
    }
    missing = [
        {
            "Id": 1103,
            "Name": "Bui Tuan Anh",
            "GroupName": "06. Don Vi Bau Cu So 6",
            "Street": "12 Tran Hung Dao",
            "StreetNumber": "",
            "City": "Ha Noi",
        }
    ]

    processor.handle_event(
        {
            "event_type": "SET_START",
            "payload": {
                "display": "ATTENDANCE",
                "present_delegates": {},
                "contact_missing": missing + list(present.values()),
            },
        },
        timestamp="2026-07-09T10:15:03+07:00",
    )
    processor.handle_event(
        {
            "event_type": "GENERAL_VOTING_RESULT",
            "payload": {
                "display": "ATTENDANCE",
                "online": 1,
                "total": 2,
                "present_delegates": present,
                "contact_missing": missing,
            },
        },
        timestamp="2026-07-09T10:15:20+07:00",
    )
    processor.handle_event(
        {
            "event_type": "SET_STOP",
            "payload": {
                "display": "ATTENDANCE",
                "present_delegates": present,
                "contact_missing": missing,
            },
        },
        timestamp="2026-07-09T10:16:22+07:00",
    )

    stored_history = json.loads(history_redis.get("attendance_history"))

    assert stored_history == [
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
    assert history_redis.get("attendance_history_active") is None


def test_attendance_history_accepts_contact_voted_alias_from_contact_missing_event() -> None:
    # CONTACT_MISSING_EVENT from voting uses contact_voted (not present_delegates).
    source_redis = fakeredis.FakeStrictRedis(decode_responses=True)
    history_redis = fakeredis.FakeStrictRedis(decode_responses=True)
    processor = VoteHistoryProcessor(source_redis=source_redis, history_redis=history_redis)

    processor.handle_event(
        {"event_type": "SET_START", "payload": {"display": "ATTENDANCE"}},
        timestamp="2026-07-09T10:15:03+07:00",
    )
    processor.handle_event(
        {
            "event_type": "CONTACT_MISSING_EVENT",
            "payload": {
                "display": "CONTACT_MISSING",
                "contact_voted": {
                    "1200": {
                        "Id": 1200,
                        "Name": "Nguyen Duy Chinh",
                        "GroupName": "10. Don Vi Bau Cu So 10",
                        "Street": "",
                        "StreetNumber": "",
                        "City": "",
                    }
                },
                "contact_missing": [
                    {
                        "Id": 1103,
                        "Name": "Bui Tuan Anh",
                        "GroupName": "06. Don Vi Bau Cu So 6",
                        "Street": "12 Tran Hung Dao",
                        "StreetNumber": "",
                        "City": "Ha Noi",
                    }
                ],
            },
        },
        timestamp="2026-07-09T10:16:22+07:00",
    )

    stored_history = json.loads(history_redis.get("attendance_history"))
    assert stored_history[0]["present"][0]["delegate_id"] == 1200
    assert stored_history[0]["missing"][0]["delegate_id"] == 1103
    assert history_redis.get("attendance_history_active") is None


def test_attendance_set_clear_discards_active_and_completed_history() -> None:
    source_redis = fakeredis.FakeStrictRedis(decode_responses=True)
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
                    "present": [],
                    "missing": [],
                }
            ]
        ),
    )
    processor = VoteHistoryProcessor(source_redis=source_redis, history_redis=history_redis)

    processor.handle_event(
        {"event_type": "SET_START", "payload": {"display": "ATTENDANCE"}},
        timestamp="2026-07-09T11:00:00+07:00",
    )
    processor.handle_event(
        {"event_type": "SET_CLEAR", "payload": {"display": "ATTENDANCE"}},
    )

    assert history_redis.get("attendance_history_active") is None
    assert history_redis.get("attendance_history") is None


def test_processor_recovers_incomplete_vote_session_on_startup() -> None:
    source_redis = fakeredis.FakeStrictRedis(decode_responses=True)
    history_redis = fakeredis.FakeStrictRedis(decode_responses=True)
    source_redis.set(
        "voting_result",
        json.dumps(
            {
                "contact": {
                    "1103": {
                        "Id": 1103,
                        "Name": "Bui Tuan Anh",
                        "GroupName": "06. Don Vi Bau Cu So 6",
                        "Street": "",
                        "StreetNumber": "",
                        "City": "",
                    }
                },
                "contact_missing": [],
                "vote": {"ATTENDANCE": [], "VOTE": []},
            }
        ),
    )
    history_redis.set(
        "vote_history_active",
        json.dumps(
            {
                "vote_index": 1,
                "started_at": "2026-07-09T11:15:03+07:00",
                "items_by_delegate": {"1103": "Tan thanh"},
            }
        ),
    )

    processor = VoteHistoryProcessor(source_redis=source_redis, history_redis=history_redis)

    processor.recover_active_sessions(timestamp="2026-07-09T11:20:00+07:00")

    stored_history = json.loads(history_redis.get("vote_history"))
    assert stored_history == [
        {
            "vote_index": 1,
            "started_at": "2026-07-09T11:15:03+07:00",
            "ended_at": "2026-07-09T11:20:00+07:00",
            "duration_seconds": 297,
            "status": "incomplete_recovered",
            "items": [
                {
                    "delegate_id": 1103,
                    "delegate_name": "Bui Tuan Anh",
                    "delegate_address": "",
                    "delegate_group_name": "06. Don Vi Bau Cu So 6",
                    "delegate_street": "",
                    "delegate_street_number": "",
                    "delegate_city": "",
                    "result": "Tan thanh",
                }
            ],
        }
    ]
    assert history_redis.get("vote_history_active") is None


def test_discuss_history_processor_tracks_waiting_and_talking() -> None:
    source_redis = fakeredis.FakeStrictRedis(decode_responses=True)
    history_redis = fakeredis.FakeStrictRedis(decode_responses=True)
    processor = VoteHistoryProcessor(source_redis=source_redis, history_redis=history_redis)

    processor.handle_event(
        {"event_type": "SET_START", "payload": {"display": "DISCUSS"}},
        timestamp="2026-07-09T14:00:00+07:00",
    )
    processor.handle_event(
        {
            "event_type": "MIC_STATE_CHANGED_IN_RUNNING_MEETING",
            "payload": {
                "display": "DISCUSS",
                "state": "On",
                "waiting": ["1103*/*Bui Tuan Anh"],
                "talking": ["1200*/*Nguyen Duy Chinh"],
                "waiting_delegates": [{"id": 1103, "display": "Bui Tuan Anh"}],
                "talking_delegates": [{"id": 1200, "display": "Nguyen Duy Chinh"}],
            },
        },
        timestamp="2026-07-09T14:01:00+07:00",
    )
    processor.handle_event(
        {"event_type": "SET_STOP", "payload": {"display": "DISCUSS"}},
        timestamp="2026-07-09T14:10:00+07:00",
    )

    stored_history = json.loads(history_redis.get("discuss_history"))
    assert stored_history == [
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
                    "waiting": [{"delegate_id": 1103, "display": "Bui Tuan Anh"}],
                    "talking": [{"delegate_id": 1200, "display": "Nguyen Duy Chinh"}],
                }
            ],
        }
    ]
    assert history_redis.get("discuss_history_active") is None


def test_discuss_set_clear_discards_active_and_completed_history() -> None:
    source_redis = fakeredis.FakeStrictRedis(decode_responses=True)
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
                    "waiting": [],
                    "talking": [],
                    "events": [],
                }
            ]
        ),
    )
    processor = VoteHistoryProcessor(source_redis=source_redis, history_redis=history_redis)

    processor.handle_event(
        {"event_type": "SET_START", "payload": {"display": "DISCUSS"}},
        timestamp="2026-07-09T15:00:00+07:00",
    )
    assert history_redis.get("discuss_history_active") is not None

    processor.handle_event(
        {"event_type": "SET_CLEAR", "payload": {"display": "DISCUSS"}},
    )

    assert history_redis.get("discuss_history_active") is None
    assert history_redis.get("discuss_history") is None


def test_process_pubsub_message_ignores_invalid_json_and_logs_error(caplog) -> None:
    source_redis = fakeredis.FakeStrictRedis(decode_responses=True)
    history_redis = fakeredis.FakeStrictRedis(decode_responses=True)
    processor = VoteHistoryProcessor(source_redis=source_redis, history_redis=history_redis)

    with caplog.at_level(logging.ERROR):
        handled = process_pubsub_message(processor, "not-json")

    assert handled is False
    assert "Failed to decode monitor message" in caplog.text


def test_process_pubsub_message_catches_processor_errors(caplog) -> None:
    class BrokenProcessor:
        def handle_event(self, event, timestamp=None):
            raise RuntimeError("boom")

    with caplog.at_level(logging.ERROR):
        handled = process_pubsub_message(BrokenProcessor(), json.dumps({"event_type": "SET_START", "payload": {"display": "VOTE"}}))

    assert handled is False
    assert "Failed to process monitor message" in caplog.text


def test_listen_vote_history_retries_after_pubsub_error() -> None:
    class FakePubSub:
        def __init__(self, messages, should_fail=False):
            self.messages = messages
            self.should_fail = should_fail
            self.subscribed_channel = None

        def subscribe(self, channel):
            self.subscribed_channel = channel

        def listen(self):
            if self.should_fail:
                raise RuntimeError("redis down")
            for message in self.messages:
                yield message

    class FakeRedis:
        def __init__(self, pubsub_instance):
            self.pubsub_instance = pubsub_instance

        def pubsub(self):
            return self.pubsub_instance

        def get(self, key):
            return None

    redis_instances = deque(
        [
            FakeRedis(FakePubSub([], should_fail=True)),
            FakeRedis(FakePubSub([], should_fail=True)),
            FakeRedis(
                FakePubSub(
                    [
                        {
                            "type": "message",
                            "data": json.dumps({"event_type": "SET_START", "payload": {"display": "VOTE"}}),
                        }
                    ]
                )
            ),
            FakeRedis(
                FakePubSub(
                    [
                        {
                            "type": "message",
                            "data": json.dumps({"event_type": "SET_START", "payload": {"display": "VOTE"}}),
                        }
                    ]
                )
            ),
        ]
    )

    def fake_redis_factory(url, decode_responses=True):
        return redis_instances.popleft()

    sleeps = []

    def fake_sleep(seconds):
        sleeps.append(seconds)

    listen_vote_history(
        source_redis_url="redis://source",
        history_redis_url="redis://history",
        monitor_channel="voting_monitor_channel",
        redis_factory=fake_redis_factory,
        sleep_fn=fake_sleep,
        max_retries=2,
        stop_when_idle=True,
    )

    assert sleeps == [1]
