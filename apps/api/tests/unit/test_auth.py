import base64
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.exceptions import InvalidTag
from fastapi.testclient import TestClient

from auth.crypto import decrypt_token, encrypt_token
from auth.deps import SESSION_COOKIE
from auth.oauth import build_authorize_url, make_state, verify_state
from auth.sessions import Session, SessionRepo
from config import Settings, get_settings
from main import app

client = TestClient(app)


def configure(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("GITHUB_CLIENT_ID", "client-id")
    monkeypatch.setenv("GITHUB_APP_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("API_BASE_URL", "http://testserver")
    monkeypatch.setenv("WEB_ORIGIN", "http://localhost:3000")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    get_settings.cache_clear()
    return get_settings()


def github_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/login/oauth/access_token":
        return httpx.Response(200, json={"access_token": "gho_test_token"})
    if request.url.path == "/user":
        return httpx.Response(200, json={"id": 7, "login": "octocat"})
    if request.url.path == "/user/installations":
        return httpx.Response(200, json={"installations": [{"id": 123}]})
    return httpx.Response(404)


def set_cookie_line(headers: list[str], name: str) -> str:
    return next(line for line in headers if line.startswith(f"{name}="))


def test_token_encryption_roundtrip_and_tamper() -> None:
    blob = encrypt_token("gho_plain_token", "secret")
    assert blob != "gho_plain_token"
    assert decrypt_token(blob, "secret") == "gho_plain_token"

    raw = bytearray(base64.urlsafe_b64decode(blob.encode("ascii")))
    raw[-1] ^= 1
    tampered = base64.urlsafe_b64encode(bytes(raw)).decode("ascii")
    with pytest.raises(InvalidTag):
        decrypt_token(tampered, "secret")


def test_session_expiry_and_one_active_session_per_user() -> None:
    repo = SessionRepo()
    expired = repo.create(github_user_id=1, github_login="a", encrypted_token="e",
                          installation_id=1, ttl_seconds=-1)
    assert repo.get(expired.id) is None

    first = repo.create(github_user_id=1, github_login="a", encrypted_token="e",
                        installation_id=1)
    second = repo.create(github_user_id=1, github_login="a", encrypted_token="e",
                         installation_id=1)
    assert repo.get(first.id) is None
    assert repo.get(second.id) is not None


def test_state_signature() -> None:
    state = make_state("secret")
    assert verify_state(state, "secret")
    assert not verify_state(state, "other-secret")
    assert not verify_state("not-a-state", "secret")


def test_authorize_url_and_state_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = configure(monkeypatch)
    url = build_authorize_url(settings, "state-value")
    assert url.startswith("https://github.com/login/oauth/authorize?")
    assert "redirect_uri=http%3A%2F%2Ftestserver%2Fauth%2Fcallback" in url

    response = client.get("/auth/github", follow_redirects=False)
    assert response.status_code == 302
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["client_id"] == ["client-id"]
    assert query["state"][0] == response.cookies.get("__Host-oauth_state")

    line = set_cookie_line(response.headers.get_list("set-cookie"), "__Host-oauth_state")
    assert "HttpOnly" in line
    assert "Secure" in line
    assert "samesite=lax" in line.lower()


def test_callback_sets_secure_cookie_and_logout(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = configure(monkeypatch)
    app.state.oauth_client = httpx.AsyncClient(transport=httpx.MockTransport(github_handler))

    start = client.get("/auth/github", follow_redirects=False)
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    response = client.get(
        "/auth/callback",
        params={"code": "code-123", "state": state},
        cookies={"__Host-oauth_state": state},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:3000/dashboard"

    line = set_cookie_line(response.headers.get_list("set-cookie"), SESSION_COOKIE)
    assert "HttpOnly" in line
    assert "Secure" in line
    assert "samesite=lax" in line.lower()
    assert "Max-Age=86400" in line
    assert "Path=/" in line
    assert "Domain=" not in line

    session_id = response.cookies.get(SESSION_COOKIE)
    assert session_id is not None
    session = app.state.sessions.get(session_id)
    assert isinstance(session, Session)
    assert session.github_login == "octocat"
    assert session.github_user_id == 7
    assert session.installation_id == 123
    assert session.encrypted_token != "gho_test_token"
    assert decrypt_token(session.encrypted_token,
                         settings.session_secret.get_secret_value()) == "gho_test_token"

    info = client.get("/auth/session", cookies={SESSION_COOKIE: session_id})
    assert info.json() == {
        "authenticated": True,
        "github_login": "octocat",
        "github_user_id": 7,
    }

    logout = client.post("/auth/logout", cookies={SESSION_COOKIE: session_id})
    assert logout.status_code == 200
    assert logout.json() == {"status": "logged_out"}
    assert app.state.sessions.get(session_id) is None


def test_callback_rejects_forged_state(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)
    response = client.get(
        "/auth/callback",
        params={"code": "code-123", "state": "forged"},
        cookies={"__Host-oauth_state": "forged"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "error=oauth_state" in response.headers["location"]
    assert SESSION_COOKIE not in response.cookies


def test_session_endpoint_without_cookie() -> None:
    response = client.get("/auth/session")
    assert response.status_code == 200
    assert response.json() == {"authenticated": False}
