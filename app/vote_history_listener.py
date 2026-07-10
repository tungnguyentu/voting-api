import json
import logging
import time
from datetime import datetime
from typing import Any, Callable, Optional

from redis import Redis

from app.config import (
    ACTIVE_ATTENDANCE_KEY,
    ACTIVE_DISCUSS_KEY,
    ACTIVE_VOTE_KEY,
    DELEGATE_DIRECTORY_KEY,
    HISTORY_ATTENDANCE_KEY,
    HISTORY_DISCUSS_KEY,
    HISTORY_REDIS_URL,
    HISTORY_VOTE_KEY,
    MONITOR_CHANNEL,
    SOURCE_REDIS_URL,
    SOURCE_VOTING_RESULT_KEY,
)
from app.redis_client import create_redis_client

log = logging.getLogger("vote_history_listener")

DISCUSS_DISPLAYS = frozenset({"DISCUSS", "CHAT"})
MIC_STATE_EVENT = "MIC_STATE_CHANGED_IN_RUNNING_MEETING"


class VoteHistoryProcessor:
    def __init__(
        self,
        source_redis: Any,
        history_redis: Any,
        source_voting_result_key: str = SOURCE_VOTING_RESULT_KEY,
        history_vote_key: str = HISTORY_VOTE_KEY,
        history_attendance_key: str = HISTORY_ATTENDANCE_KEY,
        history_discuss_key: str = HISTORY_DISCUSS_KEY,
        active_vote_key: str = ACTIVE_VOTE_KEY,
        active_attendance_key: str = ACTIVE_ATTENDANCE_KEY,
        active_discuss_key: str = ACTIVE_DISCUSS_KEY,
        delegate_directory_key: str = DELEGATE_DIRECTORY_KEY,
    ) -> None:
        self.source_redis = source_redis
        self.history_redis = history_redis
        self.source_voting_result_key = source_voting_result_key
        self.history_vote_key = history_vote_key
        self.history_attendance_key = history_attendance_key
        self.history_discuss_key = history_discuss_key
        self.active_vote_key = active_vote_key
        self.active_attendance_key = active_attendance_key
        self.active_discuss_key = active_discuss_key
        self.delegate_directory_key = delegate_directory_key

    def handle_event(self, event: dict[str, Any], timestamp: Optional[str] = None) -> None:
        if not self._is_valid_event(event):
            log.warning("Ignoring invalid monitor event: %s", event)
            return

        event_type = event.get("event_type")
        payload = event.get("payload", {})
        display = payload.get("display")
        event_time = timestamp or datetime.now().astimezone().isoformat()

        if event_type == "SET_START" and display == "ATTENDANCE":
            self.start_attendance_session(event_time)
            return

        if event_type == "SET_START" and display == "VOTE":
            self.start_vote_session(event_time)
            return

        if event_type == "SET_START" and display in DISCUSS_DISPLAYS:
            self.start_discuss_session(event_time, display=display)
            return

        if event_type == "GENERAL_VOTING_RESULT" and display == "VOTE":
            self.update_vote_results(payload)
            return

        # Voting app now publishes live present/missing on attendance GENERAL_VOTING_RESULT.
        if event_type == "GENERAL_VOTING_RESULT" and display == "ATTENDANCE":
            self.update_attendance_snapshot(payload)
            return

        if event_type == MIC_STATE_EVENT and display in DISCUSS_DISPLAYS:
            self.update_discuss_state(payload, event_time)
            return

        # Voting app finalizes attendance on SET_STOP with present_delegates + contact_missing.
        if event_type == "SET_STOP" and display == "ATTENDANCE":
            self.finish_attendance_session(payload, ended_at=event_time)
            return

        if event_type == "SET_STOP" and display == "VOTE":
            self.finish_vote_session(event_time)
            return

        if event_type == "SET_STOP" and display in DISCUSS_DISPLAYS:
            self.finish_discuss_session(event_time)
            return

        if event_type == "SET_CLEAR" and display == "ATTENDANCE":
            self.clear_attendance_session()
            return

        if event_type == "SET_CLEAR" and display == "VOTE":
            self.clear_vote_session()
            return

        if event_type == "SET_CLEAR" and display in DISCUSS_DISPLAYS:
            self.clear_discuss_session()
            return

        # CONTACT_MISSING screen may re-emit lists (field name: contact_voted).
        # Only finalize if an active attendance session still exists (e.g. older clients).
        if event_type == "CONTACT_MISSING_EVENT":
            self.finish_attendance_session(payload, ended_at=event_time)

    def recover_active_sessions(self, timestamp: Optional[str] = None) -> None:
        recovery_time = timestamp or datetime.now().astimezone().isoformat()

        active_vote = self._load_json(self.active_vote_key)
        if active_vote:
            log.warning("Recovering incomplete vote session: %s", active_vote.get("vote_index"))
            self.finish_vote_session(recovery_time, status="incomplete_recovered")

        active_attendance = self._load_json(self.active_attendance_key)
        if active_attendance:
            log.warning("Recovering incomplete attendance session: %s", active_attendance.get("attendance_index"))
            active_attendance.setdefault("ended_at", recovery_time)
            self._finalize_attendance(active_attendance, present=[], missing=[], status="incomplete_recovered")

        active_discuss = self._load_json(self.active_discuss_key)
        if active_discuss:
            log.warning("Recovering incomplete discuss session: %s", active_discuss.get("discuss_index"))
            self.finish_discuss_session(recovery_time, status="incomplete_recovered")

    def start_attendance_session(self, started_at: str) -> None:
        history = self._load_attendance_history()
        active_attendance = {
            "attendance_index": len(history) + 1,
            "started_at": started_at,
            "present_delegates": {},
            "contact_missing": [],
        }
        self._save_json(self.active_attendance_key, active_attendance)
        # Live history: visible on API immediately after start
        self._publish_attendance_history_snapshot(active_attendance, ended_at=None, status="in_progress")

    def start_vote_session(self, started_at: str) -> None:
        history = self._load_history()
        active_vote = {
            "vote_index": len(history) + 1,
            "started_at": started_at,
            "items_by_delegate": {},
        }
        self._save_json(self.active_vote_key, active_vote)
        self._publish_vote_history_snapshot(active_vote, ended_at=None, status="in_progress")

    def start_discuss_session(self, started_at: str, display: str = "DISCUSS") -> None:
        history = self._load_discuss_history()
        active_discuss = {
            "discuss_index": len(history) + 1,
            "display": display,
            "started_at": started_at,
            "waiting": [],
            "talking": [],
            "events": [],
        }
        self._save_json(self.active_discuss_key, active_discuss)
        self._publish_discuss_history_snapshot(active_discuss, ended_at=None, status="in_progress")

    def update_discuss_state(self, payload: dict[str, Any], event_time: str) -> None:
        active_discuss = self._load_json(self.active_discuss_key)
        # Mic events can arrive without SET_START (listener restart, missed start).
        # Auto-open an in-progress session so GET /history/discuss still gets live data.
        if not active_discuss:
            display = payload.get("display") or "DISCUSS"
            log.info(
                "No active discuss session; creating one from MIC event (display=%s)",
                display,
            )
            self.start_discuss_session(event_time, display=display)
            active_discuss = self._load_json(self.active_discuss_key)
            if not active_discuss:
                return

        waiting = self._normalize_discuss_delegates(
            payload.get("waiting_delegates"),
            payload.get("waiting"),
        )
        talking = self._normalize_discuss_delegates(
            payload.get("talking_delegates"),
            payload.get("talking"),
        )
        active_discuss["waiting"] = waiting
        active_discuss["talking"] = talking
        events = list(active_discuss.get("events") or [])
        events.append(
            {
                "at": event_time,
                "state": payload.get("state"),
                "waiting": waiting,
                "talking": talking,
            }
        )
        active_discuss["events"] = events
        self._save_json(self.active_discuss_key, active_discuss)
        # Continuous upsert so GET /history/discuss sees live waiting/talking
        self._publish_discuss_history_snapshot(active_discuss, ended_at=None, status="in_progress")

    def finish_discuss_session(self, ended_at: str, status: Optional[str] = None) -> None:
        active_discuss = self._load_json(self.active_discuss_key)
        if not active_discuss:
            return

        self._publish_discuss_history_snapshot(
            active_discuss,
            ended_at=ended_at,
            status=status,
        )
        self.history_redis.delete(self.active_discuss_key)

    def clear_discuss_session(self) -> None:
        """SET_CLEAR(display=DISCUSS|CHAT): drop active + completed discuss history."""
        self.history_redis.delete(self.active_discuss_key)
        self.history_redis.delete(self.history_discuss_key)

    def clear_vote_session(self) -> None:
        """SET_CLEAR(display=VOTE): drop active + completed vote history."""
        self.history_redis.delete(self.active_vote_key)
        self.history_redis.delete(self.history_vote_key)

    def update_attendance_snapshot(self, payload: dict[str, Any]) -> None:
        """Store latest present/missing while attendance is running (from voting app)."""
        active_attendance = self._load_json(self.active_attendance_key)
        if not active_attendance:
            return

        present_delegates, contact_missing = self._extract_attendance_lists(payload)
        if present_delegates is None and contact_missing is None:
            return

        if present_delegates is not None:
            active_attendance["present_delegates"] = present_delegates
        if contact_missing is not None:
            active_attendance["contact_missing"] = contact_missing
        self._save_json(self.active_attendance_key, active_attendance)
        # Continuous upsert so GET /history/attendance sees live present/missing
        self._publish_attendance_history_snapshot(active_attendance, ended_at=None, status="in_progress")

    def clear_attendance_session(self) -> None:
        """SET_CLEAR(display=ATTENDANCE): drop active + completed attendance history."""
        self.history_redis.delete(self.active_attendance_key)
        self.history_redis.delete(self.history_attendance_key)

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
        # Continuous upsert so GET /history/vote sees ballots before Stop
        self._publish_vote_history_snapshot(active_vote, ended_at=None, status="in_progress")

    def finish_vote_session(self, ended_at: str, status: Optional[str] = None) -> None:
        active_vote = self._load_json(self.active_vote_key)
        if not active_vote:
            return

        self._publish_vote_history_snapshot(active_vote, ended_at=ended_at, status=status)
        self.history_redis.delete(self.active_vote_key)

    def finish_attendance_session(
        self,
        payload: dict[str, Any],
        ended_at: Optional[str] = None,
        status: Optional[str] = None,
    ) -> None:
        active_attendance = self._load_json(self.active_attendance_key)
        if not active_attendance:
            return

        payload_present, payload_missing = self._extract_attendance_lists(payload)
        # Prefer payload from voting (SET_STOP / CONTACT_MISSING / live snapshot),
        # fall back to values cached on the active session during GENERAL_VOTING_RESULT.
        present_delegates = (
            payload_present
            if payload_present is not None
            else active_attendance.get("present_delegates") or {}
        )
        contact_missing = (
            payload_missing
            if payload_missing is not None
            else active_attendance.get("contact_missing") or []
        )

        present = sorted(
            (
                {**self._contact_to_record(contact, fallback_id=contact_id), "result": "diemdanh"}
                for contact_id, contact in present_delegates.items()
                if isinstance(contact, dict)
            ),
            key=lambda record: record["delegate_id"],
        )
        missing = sorted(
            (
                self._contact_to_record(contact)
                for contact in contact_missing
                if isinstance(contact, dict)
            ),
            key=lambda record: record["delegate_id"],
        )

        if ended_at:
            active_attendance["ended_at"] = ended_at

        self._finalize_attendance(active_attendance, present, missing, status)

    def _finalize_attendance(
        self,
        active_attendance: dict[str, Any],
        present: list[dict[str, Any]],
        missing: list[dict[str, Any]],
        status: Optional[str] = None,
    ) -> None:
        # Keep present/missing on active for snapshot builder, then finalize.
        active_attendance["present"] = present
        active_attendance["missing"] = missing
        ended_at = active_attendance.get("ended_at") or datetime.now().astimezone().isoformat()
        self._publish_attendance_history_snapshot(
            active_attendance,
            ended_at=ended_at,
            status=status,
            present=present,
            missing=missing,
        )
        self.history_redis.delete(self.active_attendance_key)

    def _publish_vote_history_snapshot(
        self,
        active_vote: dict[str, Any],
        ended_at: Optional[str],
        status: Optional[str] = None,
    ) -> None:
        self.refresh_delegate_directory()
        directory = self._load_json(self.delegate_directory_key) or {}
        items = []
        for delegate_id, result in active_vote.get("items_by_delegate", {}).items():
            delegate = directory.get(str(delegate_id), {})
            try:
                parsed_id = int(delegate_id)
            except (TypeError, ValueError):
                parsed_id = delegate_id
            items.append(self._build_vote_item(parsed_id, delegate, result))

        started_at = active_vote["started_at"]
        history_item: dict[str, Any] = {
            "vote_index": active_vote["vote_index"],
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_seconds": (
                self._duration_seconds(started_at, ended_at) if ended_at else None
            ),
            "items": items,
        }
        if status:
            history_item["status"] = status
        self._upsert_history_item(self.history_vote_key, "vote_index", history_item)

    def _publish_attendance_history_snapshot(
        self,
        active_attendance: dict[str, Any],
        ended_at: Optional[str],
        status: Optional[str] = None,
        present: Optional[list[dict[str, Any]]] = None,
        missing: Optional[list[dict[str, Any]]] = None,
    ) -> None:
        if present is None or missing is None:
            present_delegates = active_attendance.get("present_delegates") or {}
            contact_missing = active_attendance.get("contact_missing") or []
            present = sorted(
                (
                    {**self._contact_to_record(contact, fallback_id=contact_id), "result": "diemdanh"}
                    for contact_id, contact in present_delegates.items()
                    if isinstance(contact, dict)
                ),
                key=lambda record: record["delegate_id"],
            )
            missing = sorted(
                (
                    self._contact_to_record(contact)
                    for contact in contact_missing
                    if isinstance(contact, dict)
                ),
                key=lambda record: record["delegate_id"],
            )

        started_at = active_attendance["started_at"]
        history_item: dict[str, Any] = {
            "attendance_index": active_attendance["attendance_index"],
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_seconds": (
                self._duration_seconds(started_at, ended_at) if ended_at else None
            ),
            "present": present,
            "missing": missing,
        }
        if status:
            history_item["status"] = status
        self._upsert_history_item(self.history_attendance_key, "attendance_index", history_item)

    def _publish_discuss_history_snapshot(
        self,
        active_discuss: dict[str, Any],
        ended_at: Optional[str],
        status: Optional[str] = None,
    ) -> None:
        started_at = active_discuss["started_at"]
        history_item: dict[str, Any] = {
            "discuss_index": active_discuss["discuss_index"],
            "display": active_discuss.get("display", "DISCUSS"),
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_seconds": (
                self._duration_seconds(started_at, ended_at) if ended_at else None
            ),
            "waiting": active_discuss.get("waiting") or [],
            "talking": active_discuss.get("talking") or [],
            "events": active_discuss.get("events") or [],
        }
        if status:
            history_item["status"] = status
        self._upsert_history_item(self.history_discuss_key, "discuss_index", history_item)

    def _upsert_history_item(
        self,
        history_key: str,
        index_field: str,
        history_item: dict[str, Any],
    ) -> None:
        """Insert or replace session by index so live updates don't create duplicates."""
        history = self._load_json(history_key) or []
        if not isinstance(history, list):
            history = []
        index_value = history_item.get(index_field)
        replaced = False
        for i, existing in enumerate(history):
            if isinstance(existing, dict) and existing.get(index_field) == index_value:
                history[i] = history_item
                replaced = True
                break
        if not replaced:
            history.append(history_item)
        self._save_json(history_key, history)

    @staticmethod
    def _extract_attendance_lists(
        payload: dict[str, Any],
    ) -> tuple[Optional[dict[str, Any]], Optional[list[Any]]]:
        """Read present/missing from voting monitor payloads.

        Voting uses:
        - present_delegates on SET_START / SET_STOP / GENERAL_VOTING_RESULT(ATTENDANCE)
        - contact_voted on CONTACT_MISSING_EVENT (legacy alias)
        - contact_missing list in all of the above
        """
        present = payload.get("present_delegates")
        if present is None and "contact_voted" in payload:
            present = payload.get("contact_voted")
        if present is not None and not isinstance(present, dict):
            present = {}

        missing = payload.get("contact_missing")
        if missing is not None and not isinstance(missing, list):
            missing = []

        # Distinguish "field absent" vs "field present but empty"
        present_out = present if ("present_delegates" in payload or "contact_voted" in payload) else None
        missing_out = missing if "contact_missing" in payload else None
        return present_out, missing_out

    def refresh_delegate_directory(self) -> None:
        source_payload = self.source_redis.get(self.source_voting_result_key)
        if source_payload is None:
            log.warning("Cannot refresh delegate directory because source key '%s' is missing", self.source_voting_result_key)
            return

        data = json.loads(source_payload)
        directory = self._load_json(self.delegate_directory_key) or {}
        for delegate_id, contact in data.get("contact", {}).items():
            directory[str(delegate_id)] = self._contact_to_record(contact, fallback_id=delegate_id)

        self._save_json(self.delegate_directory_key, directory)

    def _load_history(self) -> list[dict[str, Any]]:
        return self._load_json(self.history_vote_key) or []

    def _load_attendance_history(self) -> list[dict[str, Any]]:
        return self._load_json(self.history_attendance_key) or []

    def _load_discuss_history(self) -> list[dict[str, Any]]:
        return self._load_json(self.history_discuss_key) or []

    def _load_json(self, key: str) -> Any:
        payload = self.history_redis.get(key)
        if payload is None:
            return None
        return json.loads(payload)

    def _save_json(self, key: str, value: Any) -> None:
        self.history_redis.set(key, json.dumps(value))

    @staticmethod
    def _is_valid_event(event: Any) -> bool:
        if not isinstance(event, dict):
            return False
        if not isinstance(event.get("event_type"), str):
            return False
        if not isinstance(event.get("payload"), dict):
            return False
        return True

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

    @staticmethod
    def _contact_to_record(contact: dict[str, Any], fallback_id: Any = None) -> dict[str, Any]:
        street = contact.get("Street") or ""
        street_number = contact.get("StreetNumber") or ""
        city = contact.get("City") or ""
        address_parts = [part for part in [street, street_number, city] if part]
        return {
            "delegate_id": int(contact.get("Id", fallback_id)),
            "delegate_name": contact.get("Name"),
            "delegate_address": ", ".join(address_parts),
            "delegate_group_name": contact.get("GroupName") or "",
            "delegate_street": street,
            "delegate_street_number": street_number,
            "delegate_city": city,
        }

    @staticmethod
    def _build_delegate_record(delegate: dict[str, Any]) -> dict[str, Any]:
        return {
            "delegate_id": delegate["delegate_id"],
            "delegate_name": delegate.get("delegate_name"),
            "delegate_address": delegate.get("delegate_address", ""),
            "delegate_group_name": delegate.get("delegate_group_name", ""),
            "delegate_street": delegate.get("delegate_street", ""),
            "delegate_street_number": delegate.get("delegate_street_number", ""),
            "delegate_city": delegate.get("delegate_city", ""),
        }

    def _build_vote_item(self, delegate_id: int, delegate: dict[str, Any], result: str) -> dict[str, Any]:
        return {
            **self._build_delegate_record({"delegate_id": delegate_id, **delegate}),
            "result": result,
        }

    @classmethod
    def _normalize_discuss_delegates(
        cls,
        structured: Any,
        raw_entries: Any,
    ) -> list[dict[str, Any]]:
        if isinstance(structured, list) and structured:
            normalized = []
            for item in structured:
                if not isinstance(item, dict):
                    continue
                delegate_id = item.get("id", item.get("delegate_id"))
                display = item.get("display") or item.get("delegate_name") or ""
                try:
                    parsed_id = int(delegate_id) if delegate_id is not None else None
                except (TypeError, ValueError):
                    parsed_id = delegate_id
                normalized.append({"delegate_id": parsed_id, "display": display})
            return normalized

        if not isinstance(raw_entries, list):
            return []

        result = []
        for entry in raw_entries:
            result.append(cls._parse_discuss_entry(entry))
        return result

    @staticmethod
    def _parse_discuss_entry(entry: Any) -> dict[str, Any]:
        if not isinstance(entry, str) or "*/*" not in entry:
            return {"delegate_id": None, "display": entry if entry is not None else ""}
        delegate_id, display = entry.split("*/*", 1)
        try:
            parsed_id = int(delegate_id)
        except (TypeError, ValueError):
            parsed_id = delegate_id
        return {"delegate_id": parsed_id, "display": display}


def process_pubsub_message(processor: VoteHistoryProcessor, payload: str) -> bool:
    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        log.exception("Failed to decode monitor message")
        return False

    try:
        processor.handle_event(event)
    except Exception:
        log.exception("Failed to process monitor message")
        return False

    return True


def listen_vote_history(
    source_redis_url: str = SOURCE_REDIS_URL,
    history_redis_url: str = HISTORY_REDIS_URL,
    monitor_channel: str = MONITOR_CHANNEL,
    redis_factory: Callable[..., Redis] = create_redis_client,
    sleep_fn: Callable[[float], None] = time.sleep,
    max_retries: Optional[int] = None,
    stop_when_idle: bool = False,
) -> None:
    retry_count = 0
    print('start app worker')
    while True:
        try:
            source_redis = redis_factory(source_redis_url, decode_responses=True)
            history_redis = redis_factory(history_redis_url, decode_responses=True)
            processor = VoteHistoryProcessor(source_redis=source_redis, history_redis=history_redis)
            processor.recover_active_sessions()

            subscriber = source_redis.pubsub()
            subscriber.subscribe(monitor_channel)
            retry_count = 0

            for message in subscriber.listen():
                print('receive event', message)
                if message.get("type") != "message":
                    continue

                payload = message.get("data")
                if not isinstance(payload, str):
                    log.warning("Ignoring non-string monitor payload: %s", type(payload).__name__)
                    continue

                process_pubsub_message(processor, payload)

            if stop_when_idle:
                return
        except Exception:
            retry_count += 1
            log.exception("Vote history listener crashed, retrying")
            if max_retries is not None and retry_count >= max_retries:
                raise

            backoff_seconds = min(2 ** (retry_count - 1), 30)
            sleep_fn(backoff_seconds)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    listen_vote_history()
