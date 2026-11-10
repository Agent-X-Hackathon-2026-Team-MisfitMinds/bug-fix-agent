import asyncio
from collections.abc import Iterator

import pytest

from auth.sessions import SessionRepo
from config import get_settings
from data.idempotency import IdempotencyStore
from data.run_repo import RunRepo
from data.webhook_repo import DeliveryStore
from main import app
from rate_limit import RateLimiter


@pytest.fixture(autouse=True)
def reset_app_state() -> Iterator[None]:
    get_settings.cache_clear()
    app.state.sessions = SessionRepo()
    app.state.run_repo = RunRepo()
    app.state.idempotency = IdempotencyStore()
    app.state.webhook_deliveries = DeliveryStore()
    app.state.pipeline_queue = None
    app.state.rate_limiter = RateLimiter()
    app.state.oauth_client = None
    yield
    client = getattr(app.state, "oauth_client", None)
    if client is not None:
        asyncio.run(client.aclose())
        app.state.oauth_client = None
    get_settings.cache_clear()
