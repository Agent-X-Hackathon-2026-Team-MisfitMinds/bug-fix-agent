"""In-memory sliding-window rate limiter keyed by caller and route."""
import math
import time
from collections import deque
from collections.abc import Awaitable, Callable
from threading import Lock
from typing import cast

from fastapi import Request

from auth.deps import SESSION_COOKIE
from errors import RateLimited


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            cutoff = now - window_seconds
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= limit:
                retry_after = max(1, math.ceil(hits[0] + window_seconds - now))
                raise RateLimited(retry_after=retry_after)
            hits.append(now)


def _identity(request: Request) -> str:
    cookie = request.cookies.get(SESSION_COOKIE)
    if cookie:
        return cookie
    return request.client.host if request.client else "unknown"


def rate_limit(
    scope: str,
    limit: int,
    window_seconds: int = 60,
) -> Callable[[Request], Awaitable[None]]:
    async def dependency(request: Request) -> None:
        limiter = cast(RateLimiter, request.app.state.rate_limiter)
        resource = str(request.path_params.get("run_id", ""))
        limiter.check(f"{scope}:{_identity(request)}:{resource}", limit, window_seconds)

    return dependency
