"""GitHub OAuth helpers: authorize URL, signed state, code exchange."""
import hashlib
import hmac
import secrets
import time
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel

from config import Settings
from errors import Unauthorized

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_INSTALLATIONS_URL = "https://api.github.com/user/installations"

STATE_MAX_AGE_SECONDS = 600


class GitHubUser(BaseModel):
    id: int
    login: str


def build_authorize_url(settings: Settings, state: str) -> str:
    params = {
        "client_id": settings.github_client_id,
        "redirect_uri": f"{settings.api_base_url.rstrip('/')}/auth/callback",
        "scope": "read:user",
        "state": state,
    }
    return f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"


def make_state(secret: str) -> str:
    nonce = secrets.token_urlsafe(16)
    issued_at = str(int(time.time()))
    signature = _sign_state(nonce, issued_at, secret)
    return f"{nonce}.{issued_at}.{signature}"


def _sign_state(nonce: str, issued_at: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), f"{nonce}.{issued_at}".encode("utf-8"),
                    hashlib.sha256).hexdigest()


def verify_state(state: str, secret: str) -> bool:
    parts = state.split(".")
    if len(parts) != 3:
        return False
    nonce, issued_at, signature = parts
    try:
        issued = int(issued_at)
    except ValueError:
        return False
    if abs(int(time.time()) - issued) > STATE_MAX_AGE_SECONDS:
        return False
    return hmac.compare_digest(_sign_state(nonce, issued_at, secret), signature)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}


async def exchange_code(code: str, settings: Settings, client: httpx.AsyncClient) -> str:
    response = await client.post(
        GITHUB_TOKEN_URL,
        data={
            "client_id": settings.github_client_id,
            "client_secret": settings.github_client_secret.get_secret_value(),
            "code": code,
            "redirect_uri": f"{settings.api_base_url.rstrip('/')}/auth/callback",
        },
        headers={"Accept": "application/json"},
    )
    if response.status_code != 200:
        raise Unauthorized("GitHub token exchange failed")
    data = response.json()
    token = data.get("access_token") if isinstance(data, dict) else None
    if not isinstance(token, str) or not token:
        raise Unauthorized("GitHub token exchange failed")
    return token


async def fetch_user(token: str, client: httpx.AsyncClient) -> GitHubUser:
    response = await client.get(GITHUB_USER_URL, headers=_bearer(token))
    if response.status_code != 200:
        raise Unauthorized("GitHub user lookup failed")
    data = response.json()
    if not isinstance(data, dict) or "id" not in data or "login" not in data:
        raise Unauthorized("GitHub user lookup failed")
    return GitHubUser(id=int(data["id"]), login=str(data["login"]))


async def fetch_installation_id(token: str, client: httpx.AsyncClient) -> int:
    response = await client.get(GITHUB_INSTALLATIONS_URL, headers=_bearer(token))
    if response.status_code != 200:
        return 0
    data = response.json()
    installations = data.get("installations", []) if isinstance(data, dict) else []
    if not installations:
        return 0
    return int(installations[0]["id"])
