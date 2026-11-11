"""Main FastAPI application for the bug-fix agent."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth.router import router as auth_router
from auth.sessions import SessionRepo
from config import get_settings
from data.idempotency import IdempotencyStore
from data.run_repo import RunRepo
from data.webhook_repo import DeliveryStore
from errors import register_error_handlers
from pipeline.queue import HANDLER_MODULE, HANDLER_NAME, PipelineQueue, load_handler
from rate_limit import RateLimiter
from routes.dev import router as dev_router
from routes.runs import router as runs_router
from security import add_security_headers
from webhooks.github import router as github_router

logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Start the run queue and drain it on shutdown."""
    queue = PipelineQueue(load_handler())
    application.state.pipeline_queue = queue
    if queue.handler is None:
        logger.warning(
            "pipeline handler not registered (%s.%s); runs will stay pending",
            HANDLER_MODULE,
            HANDLER_NAME,
        )
    try:
        yield
    finally:
        await queue.shutdown()
        application.state.pipeline_queue = None


app = FastAPI(
    title="Bug-Fix Agent API",
    description="API for the bug-fix agent system",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Idempotency-Key"],
)

app.state.sessions = SessionRepo()
app.state.run_repo = RunRepo()
app.state.idempotency = IdempotencyStore()
app.state.webhook_deliveries = DeliveryStore()
app.state.pipeline_queue = None
app.state.rate_limiter = RateLimiter()
app.state.oauth_client = None

register_error_handlers(app)
add_security_headers(app)
app.include_router(auth_router, tags=["auth"])
app.include_router(runs_router, tags=["runs"])
app.include_router(github_router, prefix="/webhooks", tags=["webhooks"])
if settings.environment == "development":
    app.include_router(dev_router, tags=["dev"])


@app.get("/health", tags=["root"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
