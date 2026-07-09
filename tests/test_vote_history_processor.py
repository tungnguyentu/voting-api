import json

import fakeredis

from app.vote_history_listener import VoteHistoryProcessor


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


def test_attendance_event_refreshes_delegate_directory_from_source_snapshot() -> None:
    source_redis = fakeredis.FakeStrictRedis(decode_responses=True)
    history_redis = fakeredis.FakeStrictRedis(decode_responses=True)
    source_redis.set(
        "voting_result",
        json.dumps(
            {
                "contact": {
                    "1200": {
                        "Id": 1200,
                        "Name": "Nguyen Duy Chinh",
                        "GroupName": "10. Don Vi Bau Cu So 10",
                        "Street": "",
                        "StreetNumber": "",
                        "City": "",
                    }
                },
                "contact_missing": [],
                "vote": {"ATTENDANCE": [{"1200": "diemdanh"}], "VOTE": []},
            }
        ),
    )
    processor = VoteHistoryProcessor(source_redis=source_redis, history_redis=history_redis)

    processor.handle_event(
        {
            "event_type": "GENERAL_VOTING_RESULT",
            "payload": {
                "display": "ATTENDANCE",
                "online": 1,
                "total": 1,
            },
        },
        timestamp="2026-07-09T11:10:00+07:00",
    )

    directory = json.loads(history_redis.get("delegate_directory"))

    assert directory == {
        "1200": {
            "delegate_id": 1200,
            "delegate_name": "Nguyen Duy Chinh",
            "delegate_address": "",
            "delegate_group_name": "10. Don Vi Bau Cu So 10",
            "delegate_street": "",
            "delegate_street_number": "",
            "delegate_city": "",
        }
    }


def test_attendance_history_processor_builds_present_and_missing_lists() -> None:
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
                    "1200": {
                        "Id": 1200,
                        "Name": "Nguyen Duy Chinh",
                        "GroupName": "10. Don Vi Bau Cu So 10",
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
            "payload": {"display": "ATTENDANCE"},
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
            },
        },
        timestamp="2026-07-09T10:15:20+07:00",
    )
    processor.handle_event(
        {
            "event_type": "SET_STOP",
            "payload": {"display": "ATTENDANCE"},
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
