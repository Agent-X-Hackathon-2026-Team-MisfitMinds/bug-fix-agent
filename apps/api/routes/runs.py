"""Run list, detail, SSE timeline and retry routes."""
import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse

from auth.deps import require_auth
from auth.sessions import Session
from data.idempotency import IdempotencyStore
from data.run_repo import Caller, RunRepo
from errors import ConflictError, ValidationFailed
from rate_limit import rate_limit
from schemas import (
    ListRunsParams,
    RetryResponse,
    RunDetail,
    RunListResponse,
    RunStatus,
    RunSummary,
)

router = APIRouter()

TERMINAL_STATES = {RunStatus.completed, RunStatus.failed, RunStatus.could_not_reproduce}


def get_run_repo(request: Request) -> RunRepo:
    return cast(RunRepo, request.app.state.run_repo)


def get_idempotency_store(request: Request) -> IdempotencyStore:
    return cast(IdempotencyStore, request.app.state.idempotency)


def _caller(session: Session) -> Caller:
    return Caller(installation_id=session.installation_id,
                  github_login=session.github_login)


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


@router.get("/runs", response_model=RunListResponse)
async def list_runs(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=256),
    status: RunStatus | None = Query(None),
    session: Session = Depends(require_auth),
    _: None = Depends(rate_limit("runs-list", 60)),
) -> RunListResponse:
    params = ListRunsParams(limit=limit, cursor=cursor, status=status)
    runs, next_cursor = get_run_repo(request).list(
        _caller(session),
        limit=params.limit,
        cursor=params.cursor,
        status=params.status,
    )
    return RunListResponse(
        data=[RunSummary.model_validate(run.model_dump()) for run in runs],
        next_cursor=next_cursor,
        has_more=next_cursor is not None,
    )


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(
    run_id: UUID,
    request: Request,
    session: Session = Depends(require_auth),
    _: None = Depends(rate_limit("runs-detail", 60)),
) -> RunDetail:
    repo = get_run_repo(request)
    caller = _caller(session)
    run = repo.get(caller, run_id)
    steps = repo.get_steps(caller, run_id)
    return RunDetail(**run.model_dump(), steps=steps)


@router.get("/runs/{run_id}/events")
async def run_events(
    run_id: UUID,
    request: Request,
    session: Session = Depends(require_auth),
    _: None = Depends(rate_limit("runs-events", 30)),
) -> StreamingResponse:
    repo = get_run_repo(request)
    caller = _caller(session)
    repo.get(caller, run_id)

    async def stream() -> AsyncIterator[str]:
        sent_steps = 0
        last_status: RunStatus | None = None
        while True:
            run = repo.get(caller, run_id)
            steps = repo.get_steps(caller, run_id)
            if run.status != last_status:
                yield _sse("run_status_changed",
                           {"run_id": str(run.id), "status": run.status.value})
                last_status = run.status
            for step in steps[sent_steps:]:
                yield _sse("step_updated", step.model_dump(mode="json"))
            sent_steps = len(steps)
            if run.status in TERMINAL_STATES:
                break
            if await request.is_disconnected():
                break
            await asyncio.sleep(1)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/runs/{run_id}/retry", response_model=RetryResponse)
async def retry_run(
    run_id: UUID,
    request: Request,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    session: Session = Depends(require_auth),
    _: None = Depends(rate_limit("runs-retry", 5)),
) -> RetryResponse:
    if not idempotency_key:
        raise ValidationFailed("Idempotency-Key header is required")

    repo = get_run_repo(request)
    store = get_idempotency_store(request)
    caller = _caller(session)
    key = f"{session.github_login}:{idempotency_key}"

    stored = store.get(key)
    if stored is not None:
        if stored.run_id != run_id:
            raise ConflictError("Idempotency-Key was already used for a different run")
        return RetryResponse(**stored.response)

    run = repo.check_retryable(caller, run_id)
    repo.reset_for_retry(run.id)
    retry = RetryResponse(run_id=run.id)
    store.put(key, run.id, retry.model_dump(mode="json"))
    return retry
