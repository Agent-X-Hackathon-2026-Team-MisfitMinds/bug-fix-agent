import asyncio
from collections.abc import Iterator

import pytest

from auth.sessions import SessionRepo
from config import get_settings
from main import app


@pytest.fixture(autouse=True)
def reset_app_state() -> Iterator[None]:
    get_settings.cache_clear()
    app.state.sessions = SessionRepo()
    app.state.oauth_client = None
    yield
    client = getattr(app.state, "oauth_client", None)
    if client is not None:
        asyncio.run(client.aclose())
        app.state.oauth_client = None
    get_settings.cache_clear()
