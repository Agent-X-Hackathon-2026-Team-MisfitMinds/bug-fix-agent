"""Dev-only helpers for frontend integration testing.

Registered only when settings.environment == "development" (see main.py).
Seeded runs are per-user (the caller's installation_id + login), so a
frontend developer can exercise list/detail/SSE/retry against realistic
data before the real pipeline is wired to the run store.
"""
from datetime import datetime, timezone
from typing import Optional, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from auth.deps import require_auth
from auth.sessions import Session
from data.run_repo import Caller, RunRepo
from schemas import (
    ConfidenceLevel,
    PipelineStep,
    Run,
    RunListResponse,
    RunStatus,
    RunStep,
    RunSummary,
    StepStatus,
)

router = APIRouter()

DEMO_REPO = "Agent-X-Hackathon-2026-Team-MisfitMinds/seeded-demo-repo"


def _step(
    run_id: UUID,
    step: PipelineStep,
    status: StepStatus,
    output: Optional[str] = None,
    error: Optional[str] = None,
) -> RunStep:
    now = datetime.now(timezone.utc)
    return RunStep(
        run_id=run_id,
        step=step,
        status=status,
        started_at=now,
        completed_at=now if status != StepStatus.running else None,
        output=output,
        error=error,
    )


@router.post("/dev/seed-runs", response_model=RunListResponse)
async def seed_runs(
    request: Request,
    session: Session = Depends(require_auth),
) -> RunListResponse:
    repo = cast(RunRepo, request.app.state.run_repo)

    def new_run(issue_number: int, title: str, body: str) -> Run:
        return repo.create(
            installation_id=session.installation_id,
            repository_full_name=DEMO_REPO,
            issue_number=issue_number,
            issue_title=title,
            issue_body=body,
            triggered_by=session.github_login,
        )

    completed = new_run(1, "Discount calculation is off by one", "The discount applied at checkout is $1 more than it should be.")
    for step in PipelineStep:
        repo.add_step(_step(completed.id, step, StepStatus.completed, output="ok"))
    repo.update_status(
        completed.id,
        RunStatus.completed,
        confidence=ConfidenceLevel.high,
        pr_url=f"https://github.com/{DEMO_REPO}/pull/1",
        pr_number=1,
        root_cause="Off-by-one in the discount formula: price - discount + 1",
        test_output="6 passed in 2.1s",
    )

    failed = new_run(2, "Profile lookup returns None for existing users", "get_user_profile returns None even when the user exists.")
    repo.add_step(_step(failed.id, PipelineStep.read, StepStatus.completed, output="issue fetched"))
    repo.add_step(_step(failed.id, PipelineStep.reproduce, StepStatus.completed, output="2 failed, 4 passed"))
    repo.add_step(_step(failed.id, PipelineStep.diagnose, StepStatus.failed, error="LLM provider rate limit exceeded"))
    repo.update_status(failed.id, RunStatus.failed)

    cnr = new_run(3, "Age validation rejects valid ages", "validate_age rejects 21+ intermittently.")
    repo.add_step(_step(cnr.id, PipelineStep.read, StepStatus.completed, output="issue fetched"))
    repo.add_step(_step(cnr.id, PipelineStep.reproduce, StepStatus.completed, output="all 6 tests passed on a clean clone"))
    repo.update_status(cnr.id, RunStatus.could_not_reproduce, test_output="6 passed in 1.8s")

    pending = new_run(4, "Checkout total rounds down instead of up", "Rounding mode looks wrong for the checkout total.")
    repo.add_step(_step(pending.id, PipelineStep.read, StepStatus.completed, output="issue fetched"))
    repo.add_step(_step(pending.id, PipelineStep.reproduce, StepStatus.running, output="cloning repo"))

    caller = Caller(installation_id=session.installation_id, github_login=session.github_login)
    runs, next_cursor = repo.list(caller, limit=10)
    return RunListResponse(
        data=[RunSummary.model_validate(run.model_dump()) for run in runs],
        next_cursor=next_cursor,
        has_more=next_cursor is not None,
    )
