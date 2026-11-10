"""Main FastAPI application for the bug-fix agent."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth.router import router as auth_router
from auth.sessions import SessionRepo
from config import get_settings
from errors import register_error_handlers
from webhooks.github import router as github_router

settings = get_settings()

app = FastAPI(
    title="Bug-Fix Agent API",
    description="API for the bug-fix agent system",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Idempotency-Key"],
)

app.state.sessions = SessionRepo()
app.state.oauth_client = None

register_error_handlers(app)
app.include_router(auth_router, tags=["auth"])
app.include_router(github_router, prefix="/webhooks", tags=["webhooks"])


@app.get("/health", tags=["root"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
