"""Main FastAPI application for the bug-fix agent."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from errors import register_error_handlers
from webhooks.github import router as github_router

app = FastAPI(
    title="Bug-Fix Agent API",
    description="API for the bug-fix agent system",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("WEB_ORIGIN", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Idempotency-Key"],
)

register_error_handlers(app)
app.include_router(github_router, prefix="/webhooks", tags=["webhooks"])


@app.get("/health", tags=["root"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
