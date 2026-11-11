"""Main FastAPI application for the bug-fix agent."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import cast
from uuid import UUID

from fastapi import FastAPI, Request
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
from schemas import PipelineStep, RunStatus, RunStep, StepStatus
from security import add_security_headers
from webhooks.github import router as github_router

logger = logging.getLogger(__name__)

TERMINAL = {RunStatus.completed, RunStatus.failed, RunStatus.could_not_reproduce}

settings = get_settings()


def _describe(exc: BaseException) -> str:
    detail = str(exc).strip()
    return (f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__)[:500]


def mark_run_failed(application: FastAPI, run_id: UUID, exc: BaseException) -> None:
    """Record an infrastructure failure so a run never stays `pending` forever.

    The pipeline owns node-level errors; this only catches the case where the
    handler itself blew up before it could write anything.
    """
    repo = cast(RunRepo | None, getattr(application.state, "run_repo", None))
    if repo is None:
        return
    try:
        run = repo.get_by_id(run_id)
    except Exception:
        logger.warning("cannot mark run %s failed: run not found", run_id)
        return
    if run is None:
        logger.warning("cannot mark run %s failed: run not found", run_id)
        return
    if run.status in TERMINAL:
        return
    message = _describe(exc)
    now = datetime.now(timezone.utc)
    steps = repo.get_steps_by_id(run_id)
    if steps and steps[-1].status is StepStatus.running:
        repo.update_step(
            steps[-1].model_copy(
                update={"status": StepStatus.failed, "error": message, "completed_at": now}
            )
        )
    else:
        repo.add_step(
            RunStep(
                run_id=run_id,
                step=steps[-1].step if steps else PipelineStep.read,
                status=StepStatus.failed,
                error=message,
                completed_at=now,
            )
        )
    repo.update_status(run_id, RunStatus.failed)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Start the run queue and drain it on shutdown."""
    queue = PipelineQueue(
        load_handler(),
        on_error=lambda run_id, exc: mark_run_failed(application, run_id, exc),
    )
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
async def health_check(request: Request) -> dict[str, str]:
    """Liveness plus whether the pipeline can actually execute queued runs."""
    queue = getattr(request.app.state, "pipeline_queue", None)
    ready = getattr(queue, "handler", None) is not None
    return {"status": "ok", "pipeline": "ready" if ready else "no-handler"}
