"""Idempotency-Key replay protection for retry requests."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class StoredResponse:
    run_id: UUID
    response: dict[str, Any]
    expires_at: datetime


class IdempotencyStore:
    def __init__(self) -> None:
        self._entries: dict[str, StoredResponse] = {}
        self._lock = Lock()

    def get(self, key: str) -> StoredResponse | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at <= datetime.now(timezone.utc):
                del self._entries[key]
                return None
            return entry

    def put(self, key: str, run_id: UUID, response: dict[str, Any],
            ttl_seconds: int = 86400) -> StoredResponse:
        entry = StoredResponse(
            run_id=run_id,
            response=response,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
        )
        with self._lock:
            self._entries[key] = entry
        return entry
