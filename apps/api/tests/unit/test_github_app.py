import base64
import json
from datetime import datetime, timezone
from typing import Any, cast

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from config import Settings
from github_app import GitHubAppAuth, GitHubAuthError, auth_from_settings, load_private_key


@pytest.fixture(scope="module")
def private_key_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return pem.decode("ascii")


def _decode(segment: str) -> dict[str, Any]:
    padded = segment + "=" * (-len(segment) % 4)
    return cast(dict[str, Any], json.loads(base64.urlsafe_b64decode(padded)))


def _decode_signature(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def _expiry_iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_app_jwt_claims_and_signature(private_key_pem: str) -> None:
    auth = GitHubAppAuth("123456", private_key_pem, clock=lambda: 1_700_000_000.0)

    token = auth.app_jwt()
    header, claims, signature = token.split(".")

    assert _decode(header) == {"alg": "RS256", "typ": "JWT"}
    assert _decode(claims) == {
        "iat": 1_699_999_940,
        "exp": 1_700_000_540,
        "iss": "123456",
    }
    public_key = load_private_key(private_key_pem).public_key()
    public_key.verify(
        _decode_signature(signature),
        f"{header}.{claims}".encode("ascii"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )


def test_installation_token_is_cached_until_refresh_window(private_key_pem: str) -> None:
    expires_at = 1_700_003_600.0
    now = [expires_at - 3_600.0]
    requests: list[httpx.Request] = []
    issued = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        issued[0] += 1
        return httpx.Response(
            201,
            json={"token": f"ghs_{issued[0]}", "expires_at": _expiry_iso(expires_at)},
        )

    auth = GitHubAppAuth(
        "123456",
        private_key_pem,
        transport=httpx.MockTransport(handler),
        clock=lambda: now[0],
    )

    assert auth.installation_token(42) == "ghs_1"
    assert auth.installation_token(42) == "ghs_1"
    assert len(requests) == 1

    first = requests[0]
    assert str(first.url) == "https://api.github.com/app/installations/42/access_tokens"
    assert first.headers["Authorization"].startswith("Bearer ")
    assert first.headers["Accept"] == "application/vnd.github+json"

    now[0] = expires_at - 30.0
    assert auth.installation_token(42) == "ghs_2"
    assert len(requests) == 2


def test_installation_token_failure_does_not_echo_the_jwt(private_key_pem: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Bad credentials"})

    auth = GitHubAppAuth(
        "123456",
        private_key_pem,
        transport=httpx.MockTransport(handler),
        clock=lambda: 1_700_000_000.0,
    )

    with pytest.raises(GitHubAuthError) as error:
        auth.installation_token(42)

    message = str(error.value)
    assert "401" in message
    assert "Bad credentials" in message
    assert "Bearer" not in message


def test_invalidate_forces_a_new_token(private_key_pem: str) -> None:
    issued = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        issued[0] += 1
        return httpx.Response(
            201,
            json={"token": f"ghs_{issued[0]}", "expires_at": _expiry_iso(1_700_003_600.0)},
        )

    auth = GitHubAppAuth(
        "123456",
        private_key_pem,
        transport=httpx.MockTransport(handler),
        clock=lambda: 1_700_000_000.0,
    )

    assert auth.installation_token(42) == "ghs_1"
    auth.invalidate(42)
    assert auth.installation_token(42) == "ghs_2"


def test_malformed_private_key_is_rejected() -> None:
    with pytest.raises(GitHubAuthError):
        GitHubAppAuth("123456", "not-a-pem")


def test_auth_from_settings_requires_both_credentials(monkeypatch: Any) -> None:
    monkeypatch.setenv("GITHUB_APP_ID", "")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", "")

    with pytest.raises(GitHubAuthError):
        auth_from_settings(Settings())


def test_auth_from_settings_accepts_escaped_pem(monkeypatch: Any, private_key_pem: str) -> None:
    monkeypatch.setenv("GITHUB_APP_ID", "123456")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", private_key_pem.replace("\n", "\\n"))

    auth = auth_from_settings(Settings())

    assert auth.app_id == "123456"
    assert auth.app_jwt().count(".") == 2
