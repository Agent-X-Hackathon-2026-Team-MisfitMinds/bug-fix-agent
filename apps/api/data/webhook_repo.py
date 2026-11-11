"""In-memory webhook delivery dedup keyed by X-GitHub-Delivery."""
from datetime import datetime, timedelta, timezone
from threading import Lock


class DeliveryStore:
    def __init__(self, ttl_seconds: int = 86400) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._expires_at: dict[str, datetime] = {}
        self._lock = Lock()

    def check_and_add(self, delivery_id: str) -> bool:
        """Return False when this delivery was already processed."""
        now = datetime.now(timezone.utc)
        with self._lock:
            for key in [key for key, expiry in self._expires_at.items() if expiry <= now]:
                del self._expires_at[key]
            if delivery_id in self._expires_at:
                return False
            self._expires_at[delivery_id] = now + self._ttl
            return True
