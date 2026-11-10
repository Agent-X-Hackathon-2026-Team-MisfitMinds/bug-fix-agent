"""Session dependencies for protected routes."""
from typing import cast

from fastapi import Request

from auth.sessions import Session, SessionRepo
from errors import Unauthorized

SESSION_COOKIE = "__Host-session_id"


def get_session_repo(request: Request) -> SessionRepo:
    return cast(SessionRepo, request.app.state.sessions)


def require_auth(request: Request) -> Session:
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        raise Unauthorized("Not signed in")
    session = get_session_repo(request).get(session_id)
    if session is None:
        raise Unauthorized("Session expired or invalid")
    return session


def optional_auth(request: Request) -> Session | None:
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        return None
    return get_session_repo(request).get(session_id)
