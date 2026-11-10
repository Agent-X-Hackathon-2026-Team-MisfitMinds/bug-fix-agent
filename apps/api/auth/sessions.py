"""In-memory session store (ADR-006: no database in v1)."""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from threading import Lock
from uuid import uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Session:
    id: str
    github_user_id: int
    github_login: str
    encrypted_token: str
    installation_id: int
    expires_at: datetime
    created_at: datetime


class SessionRepo:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = Lock()

    def create(
        self,
        *,
        github_user_id: int,
        github_login: str,
        encrypted_token: str,
        installation_id: int,
        ttl_seconds: int = 86400,
    ) -> Session:
        now = _utcnow()
        session = Session(
            id=str(uuid4()),
            github_user_id=github_user_id,
            github_login=github_login,
            encrypted_token=encrypted_token,
            installation_id=installation_id,
            expires_at=now + timedelta(seconds=ttl_seconds),
            created_at=now,
        )
        with self._lock:
            for session_id in [sid for sid, item in self._sessions.items()
                               if item.github_user_id == github_user_id]:
                del self._sessions[session_id]
            self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if session.expires_at <= _utcnow():
                del self._sessions[session_id]
                return None
            return session

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def delete_all_for_user(self, github_user_id: int) -> int:
        with self._lock:
            ids = [sid for sid, item in self._sessions.items()
                   if item.github_user_id == github_user_id]
            for session_id in ids:
                del self._sessions[session_id]
            return len(ids)

    def replace_expiry(self, session_id: str, expires_at: datetime) -> Session | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            updated = replace(session, expires_at=expires_at)
            self._sessions[session_id] = updated
            return updated
