import json
from datetime import datetime
from typing import Any, Optional

from redis import Redis

from app.config import (
    ACTIVE_ATTENDANCE_KEY,
    ACTIVE_VOTE_KEY,
    DELEGATE_DIRECTORY_KEY,
    HISTORY_ATTENDANCE_KEY,
    HISTORY_REDIS_URL,
    HISTORY_VOTE_KEY,
    MONITOR_CHANNEL,
    SOURCE_REDIS_URL,
    SOURCE_VOTING_RESULT_KEY,
)


class VoteHistoryProcessor:
    def __init__(
        self,
        source_redis: Any,
        history_redis: Any,
        source_voting_result_key: str = SOURCE_VOTING_RESULT_KEY,
        history_vote_key: str = HISTORY_VOTE_KEY,
        history_attendance_key: str = HISTORY_ATTENDANCE_KEY,
        active_vote_key: str = ACTIVE_VOTE_KEY,
        active_attendance_key: str = ACTIVE_ATTENDANCE_KEY,
        delegate_directory_key: str = DELEGATE_DIRECTORY_KEY,
    ) -> None:
        self.source_redis = source_redis
        self.history_redis = history_redis
        self.source_voting_result_key = source_voting_result_key
        self.history_vote_key = history_vote_key
        self.history_attendance_key = history_attendance_key
        self.active_vote_key = active_vote_key
        self.active_attendance_key = active_attendance_key
        self.delegate_directory_key = delegate_directory_key

    def handle_event(self, event: dict[str, Any], timestamp: Optional[str] = None) -> None:
        event_type = event.get("event_type")
        payload = event.get("payload", {})
        display = payload.get("display")
        event_time = timestamp or datetime.now().astimezone().isoformat()

        if display == "ATTENDANCE":
            self.refresh_delegate_directory()

        if event_type == "SET_START" and display == "ATTENDANCE":
            self.start_attendance_session(event_time)
            return

        if event_type == "SET_START" and display == "VOTE":
            self.start_vote_session(event_time)
            return

        if event_type == "GENERAL_VOTING_RESULT" and display == "ATTENDANCE":
            self.update_attendance_results()
            return

        if event_type == "GENERAL_VOTING_RESULT" and display == "VOTE":
            self.update_vote_results(payload)
            return

        if event_type == "SET_STOP" and display == "ATTENDANCE":
            self.finish_attendance_session(event_time)
            return

        if event_type == "SET_STOP" and display == "VOTE":
            self.finish_vote_session(event_time)

    def start_attendance_session(self, started_at: str) -> None:
        history = self._load_attendance_history()
        active_attendance = {
            "attendance_index": len(history) + 1,
            "started_at": started_at,
            "present_delegate_ids": [],
        }
        self._save_json(self.active_attendance_key, active_attendance)

    def start_vote_session(self, started_at: str) -> None:
        history = self._load_history()
        active_vote = {
            "vote_index": len(history) + 1,
            "started_at": started_at,
            "items_by_delegate": {},
        }
        self._save_json(self.active_vote_key, active_vote)

    def update_attendance_results(self) -> None:
        active_attendance = self._load_json(self.active_attendance_key)
        if not active_attendance:
            return

        source_payload = self.source_redis.get(self.source_voting_result_key)
        if source_payload is None:
            return

        data = json.loads(source_payload)
        attendance_sessions = data.get("vote", {}).get("ATTENDANCE", [])
        if not attendance_sessions:
            return

        latest_attendance = attendance_sessions[-1]
        active_attendance["present_delegate_ids"] = sorted(
            int(delegate_id)
            for delegate_id, result in latest_attendance.items()
            if result
        )
        self._save_json(self.active_attendance_key, active_attendance)

    def update_vote_results(self, payload: dict[str, Any]) -> None:
        active_vote = self._load_json(self.active_vote_key)
        if not active_vote:
            return

        voting_options = payload.get("meeting_voting_options", {}).get("VOTE", {})
        for result in payload.get("voting_results", []):
            delegate_id = result.get("delegate_id")
            if not delegate_id:
                continue

            option = self._find_option(voting_options, result.get("voting_option_id"))
            if not option:
                continue

            active_vote["items_by_delegate"][str(delegate_id)] = option.get("Name")

        self._save_json(self.active_vote_key, active_vote)

    def finish_vote_session(self, ended_at: str) -> None:
        active_vote = self._load_json(self.active_vote_key)
        if not active_vote:
            return

        self.refresh_delegate_directory()
        directory = self._load_json(self.delegate_directory_key) or {}
        items = []
        for delegate_id, result in active_vote.get("items_by_delegate", {}).items():
            delegate = directory.get(str(delegate_id), {})
            items.append(
                {
                    "delegate_id": int(delegate_id),
                    "delegate_name": delegate.get("delegate_name"),
                    "delegate_address": delegate.get("delegate_address"),
                    "delegate_group_name": delegate.get("delegate_group_name", ""),
                    "delegate_street": delegate.get("delegate_street", ""),
                    "delegate_street_number": delegate.get("delegate_street_number", ""),
                    "delegate_city": delegate.get("delegate_city", ""),
                    "result": result,
                }
            )

        started_at = active_vote["started_at"]
        history_item = {
            "vote_index": active_vote["vote_index"],
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_seconds": self._duration_seconds(started_at, ended_at),
            "items": items,
        }

        history = self._load_history()
        history.append(history_item)
        self._save_json(self.history_vote_key, history)
        self.history_redis.delete(self.active_vote_key)

    def finish_attendance_session(self, ended_at: str) -> None:
        active_attendance = self._load_json(self.active_attendance_key)
        if not active_attendance:
            return

        self.refresh_delegate_directory()
        directory = self._load_json(self.delegate_directory_key) or {}
        present_delegate_ids = {
            str(delegate_id) for delegate_id in active_attendance.get("present_delegate_ids", [])
        }

        present = []
        missing = []
        for delegate_id, delegate in sorted(directory.items(), key=lambda item: int(item[0])):
            delegate_record = {
                "delegate_id": delegate["delegate_id"],
                "delegate_name": delegate.get("delegate_name"),
                "delegate_address": delegate.get("delegate_address", ""),
                "delegate_group_name": delegate.get("delegate_group_name", ""),
                "delegate_street": delegate.get("delegate_street", ""),
                "delegate_street_number": delegate.get("delegate_street_number", ""),
                "delegate_city": delegate.get("delegate_city", ""),
            }
            if delegate_id in present_delegate_ids:
                present.append({**delegate_record, "result": "diemdanh"})
            else:
                missing.append(delegate_record)

        started_at = active_attendance["started_at"]
        history_item = {
            "attendance_index": active_attendance["attendance_index"],
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_seconds": self._duration_seconds(started_at, ended_at),
            "present": present,
            "missing": missing,
        }

        history = self._load_attendance_history()
        history.append(history_item)
        self._save_json(self.history_attendance_key, history)
        self.history_redis.delete(self.active_attendance_key)

    def refresh_delegate_directory(self) -> None:
        source_payload = self.source_redis.get(self.source_voting_result_key)
        if source_payload is None:
            return

        data = json.loads(source_payload)
        directory = self._load_json(self.delegate_directory_key) or {}
        for delegate_id, contact in data.get("contact", {}).items():
            street = contact.get("Street") or ""
            street_number = contact.get("StreetNumber") or ""
            city = contact.get("City") or ""
            address_parts = [part for part in [street, street_number, city] if part]
            directory[str(delegate_id)] = {
                "delegate_id": int(contact.get("Id", delegate_id)),
                "delegate_name": contact.get("Name"),
                "delegate_address": ", ".join(address_parts),
                "delegate_group_name": contact.get("GroupName") or "",
                "delegate_street": street,
                "delegate_street_number": street_number,
                "delegate_city": city,
            }

        self._save_json(self.delegate_directory_key, directory)

    def _load_history(self) -> list[dict[str, Any]]:
        return self._load_json(self.history_vote_key) or []

    def _load_attendance_history(self) -> list[dict[str, Any]]:
        return self._load_json(self.history_attendance_key) or []

    def _load_json(self, key: str) -> Any:
        payload = self.history_redis.get(key)
        if payload is None:
            return None
        return json.loads(payload)

    def _save_json(self, key: str, value: Any) -> None:
        self.history_redis.set(key, json.dumps(value))

    @staticmethod
    def _find_option(voting_options: dict[str, Any], voting_option_id: Any) -> Optional[dict[str, Any]]:
        option_key = str(voting_option_id)
        if option_key in voting_options:
            return voting_options[option_key]
        if voting_option_id in voting_options:
            return voting_options[voting_option_id]
        return None

    @staticmethod
    def _duration_seconds(started_at: str, ended_at: str) -> int:
        started = datetime.fromisoformat(started_at)
        ended = datetime.fromisoformat(ended_at)
        return int((ended - started).total_seconds())


def listen_vote_history(
    source_redis_url: str = SOURCE_REDIS_URL,
    history_redis_url: str = HISTORY_REDIS_URL,
    monitor_channel: str = MONITOR_CHANNEL,
) -> None:
    source_redis = Redis.from_url(source_redis_url, decode_responses=True)
    history_redis = Redis.from_url(history_redis_url, decode_responses=True)
    processor = VoteHistoryProcessor(source_redis=source_redis, history_redis=history_redis)

    subscriber = source_redis.pubsub()
    subscriber.subscribe(monitor_channel)
    for message in subscriber.listen():
        if message.get("type") != "message":
            continue

        payload = message.get("data")
        if not isinstance(payload, str):
            continue

        processor.handle_event(json.loads(payload))


if __name__ == "__main__":
    listen_vote_history()
