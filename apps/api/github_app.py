"""GitHub App authentication: RS256 app JWT and cached installation tokens.

The private key stays in `Settings`; only short-lived installation tokens leave
this module, and they are never logged or included in error messages.
"""
import base64
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from config import Settings, get_settings

GITHUB_API = "https://api.github.com"
API_VERSION = "2022-11-28"
APP_JWT_BACKDATE_SECONDS = 60
APP_JWT_LIFETIME_SECONDS = 540
REFRESH_SKEW_SECONDS = 60


class GitHubAuthError(RuntimeError):
    """Raised when App credentials are missing or GitHub rejects the JWT."""


@dataclass(frozen=True)
class _CachedToken:
    value: str
    refresh_at: float


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _normalize_pem(value: str) -> str:
    """Accept a one-line escaped PEM as well as a real multi-line block."""
    return value.replace("\\n", "\n").strip()


def load_private_key(pem: str) -> rsa.RSAPrivateKey:
    try:
        key = serialization.load_pem_private_key(_normalize_pem(pem).encode("utf-8"), password=None)
    except (ValueError, TypeError) as exc:
        raise GitHubAuthError("GitHub App private key is not a valid PEM key") from exc
    if not isinstance(key, rsa.RSAPrivateKey):
        raise GitHubAuthError("GitHub App private key must be an RSA key")
    return key


def _parse_expiry(value: Any, now: float) -> float:
    if not isinstance(value, str):
        return now
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return now


def _error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"HTTP {response.status_code}"
    message = payload.get("message") if isinstance(payload, dict) else None
    return f"HTTP {response.status_code}: {message}" if message else f"HTTP {response.status_code}"


class GitHubAppAuth:
    """Mints app JWTs and exchanges them for installation access tokens."""

    def __init__(
        self,
        app_id: str,
        private_key: str,
        *,
        api_base: str = GITHUB_API,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not app_id.strip():
            raise GitHubAuthError("GITHUB_APP_ID is not configured")
        self.app_id = app_id.strip()
        self._key = load_private_key(private_key)
        self._api_base = api_base.rstrip("/")
        self._transport = transport
        self._clock = clock
        self._tokens: dict[int, _CachedToken] = {}

    def app_jwt(self, *, now: float | None = None) -> str:
        issued_at = int(now if now is not None else self._clock())
        header = {"alg": "RS256", "typ": "JWT"}
        claims = {
            "iat": issued_at - APP_JWT_BACKDATE_SECONDS,
            "exp": issued_at + APP_JWT_LIFETIME_SECONDS,
            "iss": self.app_id,
        }
        segments = [
            _b64url(json.dumps(part, separators=(",", ":")).encode("utf-8"))
            for part in (header, claims)
        ]
        signing_input = ".".join(segments).encode("ascii")
        signature = self._key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
        return f"{segments[0]}.{segments[1]}.{_b64url(signature)}"

    def installation_token(self, installation_id: int) -> str:
        if installation_id <= 0:
            raise GitHubAuthError("A positive installation id is required")
        now = self._clock()
        cached = self._tokens.get(installation_id)
        if cached is not None and cached.refresh_at > now:
            return cached.value

        token, expires_at = self._fetch_token(installation_id)
        self._tokens[installation_id] = _CachedToken(
            value=token,
            refresh_at=expires_at - REFRESH_SKEW_SECONDS,
        )
        return token

    def invalidate(self, installation_id: int) -> None:
        self._tokens.pop(installation_id, None)

    def _fetch_token(self, installation_id: int) -> tuple[str, float]:
        headers = {
            "Authorization": f"Bearer {self.app_jwt()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
        }
        url = f"{self._api_base}/app/installations/{installation_id}/access_tokens"
        try:
            with httpx.Client(transport=self._transport, timeout=15.0) as client:
                response = client.post(url, headers=headers)
        except httpx.HTTPError as exc:
            raise GitHubAuthError("Could not reach GitHub to mint an installation token") from exc

        if response.status_code != 201:
            raise GitHubAuthError(
                f"GitHub rejected the installation token request ({_error_message(response)})"
            )
        payload = cast(dict[str, Any], response.json())
        token = payload.get("token")
        if not isinstance(token, str) or not token:
            raise GitHubAuthError("GitHub returned no installation token")
        return token, _parse_expiry(payload.get("expires_at"), self._clock())


def auth_from_settings(settings: Settings | None = None) -> GitHubAppAuth:
    resolved = settings or get_settings()
    private_key = resolved.github_app_private_key.get_secret_value()
    if not resolved.github_app_id.strip() or not private_key.strip():
        raise GitHubAuthError(
            "GitHub App credentials are not configured (GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY)"
        )
    return GitHubAppAuth(resolved.github_app_id, private_key)
