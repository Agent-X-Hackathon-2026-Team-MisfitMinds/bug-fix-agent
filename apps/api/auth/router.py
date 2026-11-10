"""GitHub OAuth and session routes."""
import hmac
from typing import Any, cast

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from auth.crypto import encrypt_token
from auth.deps import SESSION_COOKIE, get_session_repo, optional_auth
from auth.oauth import (
    build_authorize_url,
    exchange_code,
    fetch_installation_id,
    fetch_user,
    make_state,
    verify_state,
)
from auth.sessions import Session
from config import Settings, get_settings
from errors import Unauthorized
from schemas import LogoutResponse, SessionInfo

router = APIRouter()

OAUTH_STATE_COOKIE = "__Host-oauth_state"


def _cookie_kwargs(settings: Settings) -> dict[str, Any]:
    return {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": "lax",
        "path": "/",
    }


def _start_response(settings: Settings, state: str) -> RedirectResponse:
    response = RedirectResponse(build_authorize_url(settings, state), status_code=302)
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        state,
        max_age=settings.oauth_state_ttl_seconds,
        **_cookie_kwargs(settings),
    )
    return response


def _error_redirect(settings: Settings, code: str) -> RedirectResponse:
    response = RedirectResponse(
        f"{settings.web_origin.rstrip('/')}/auth/github?error={code}",
        status_code=302,
    )
    response.delete_cookie(OAUTH_STATE_COOKIE, **_cookie_kwargs(settings))
    return response


def _finish_response(settings: Settings, session: Session) -> RedirectResponse:
    response = RedirectResponse(
        f"{settings.web_origin.rstrip('/')}/dashboard",
        status_code=302,
    )
    response.set_cookie(
        SESSION_COOKIE,
        session.id,
        max_age=settings.session_ttl_seconds,
        **_cookie_kwargs(settings),
    )
    response.delete_cookie(OAUTH_STATE_COOKIE, **_cookie_kwargs(settings))
    return response


@router.get("/auth/github")
async def start_oauth() -> RedirectResponse:
    settings = get_settings()
    secret = settings.session_secret.get_secret_value()
    return _start_response(settings, make_state(secret))


@router.get("/auth/callback")
async def oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
) -> RedirectResponse:
    settings = get_settings()
    secret = settings.session_secret.get_secret_value()
    state_cookie = request.cookies.get(OAUTH_STATE_COOKIE)
    if (
        not code
        or not state
        or not state_cookie
        or not hmac.compare_digest(state.encode("utf-8"), state_cookie.encode("utf-8"))
        or not verify_state(state, secret)
    ):
        return _error_redirect(settings, "oauth_state")

    client: httpx.AsyncClient
    injected = getattr(request.app.state, "oauth_client", None)
    owns_client = injected is None
    if injected is None:
        client = httpx.AsyncClient(timeout=10.0)
    else:
        client = cast(httpx.AsyncClient, injected)
    try:
        token = await exchange_code(code, settings, client)
        user = await fetch_user(token, client)
        installation_id = await fetch_installation_id(token, client)
    except (Unauthorized, httpx.HTTPError, ValueError):
        return _error_redirect(settings, "oauth_failed")
    finally:
        if owns_client:
            await client.aclose()

    session = get_session_repo(request).create(
        github_user_id=user.id,
        github_login=user.login,
        encrypted_token=encrypt_token(token, secret),
        installation_id=installation_id,
        ttl_seconds=settings.session_ttl_seconds,
    )
    return _finish_response(settings, session)


@router.get("/auth/session", response_model=SessionInfo, response_model_exclude_none=True)
async def session_info(request: Request) -> SessionInfo:
    session = optional_auth(request)
    if session is None:
        return SessionInfo(authenticated=False)
    return SessionInfo(
        authenticated=True,
        github_login=session.github_login,
        github_user_id=session.github_user_id,
    )


@router.post("/auth/logout", response_model=LogoutResponse)
async def logout(request: Request) -> Response:
    settings = get_settings()
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        raise Unauthorized("Not signed in")
    repo = get_session_repo(request)
    if repo.get(session_id) is None:
        raise Unauthorized("Not signed in")
    repo.delete(session_id)
    response = JSONResponse({"status": "logged_out"})
    response.delete_cookie(SESSION_COOKIE, **_cookie_kwargs(settings))
    return response
