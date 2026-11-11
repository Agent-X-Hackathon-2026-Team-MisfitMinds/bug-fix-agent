"""Run handler discovered by `pipeline.queue` as `pipeline.runner.handle_run`.

Executes the stages that work today (read, reproduce baseline) and always
leaves the run in a real terminal state. Diagnose, fix, verify and PR are not
wired yet, so a reproducible run ends as `failed` with a clear step error
instead of an invented result.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import cast
from uuid import UUID

from data.run_repo import RunRepo
from pipeline.github_client import client_for
from pipeline.sandbox import (
    SandboxConfig,
    clone_and_test_async,
    container_name,
    repository_url,
)
from schemas import PipelineStep, RunStatus, RunStep, StepStatus

MIN_ISSUE_BODY_CHARS = 50
MAX_OUTPUT_CHARS = 2000
NEED_MORE_INFO = (
    "Need more reproduction information. Please provide reproduction steps, "
    "expected behaviour and actual behaviour."
)
NOT_AVAILABLE = "diagnose and fix stages are not available yet"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _run_repo() -> RunRepo:
    # main imports pipeline.queue, which loads this module; import late to avoid a cycle.
    from main import app

    return cast(RunRepo, app.state.run_repo)


def _start(repo: RunRepo, run_id: UUID, step: PipelineStep) -> RunStep:
    record = RunStep(run_id=run_id, step=step, status=StepStatus.running, started_at=_now())
    repo.add_step(record)
    return record


def _finish(
    repo: RunRepo, step: RunStep, *, output: str | None = None, error: str | None = None
) -> None:
    status = StepStatus.failed if error else StepStatus.completed
    repo.update_step(
        step.model_copy(
            update={"status": status, "output": output, "error": error, "completed_at": _now()}
        )
    )


async def handle_run(run_id: UUID) -> None:
    repo = _run_repo()
    run = repo.get_by_id(run_id)

    read = _start(repo, run_id, PipelineStep.read)
    if len(run.issue_body.strip()) < MIN_ISSUE_BODY_CHARS:
        note = "issue is too thin to reproduce"
        try:
            client = client_for(run.installation_id, run.repository_full_name)
            await client.add_issue_comment(run.issue_number, NEED_MORE_INFO)
            note += "; comment posted"
        except Exception as exc:  # GitHub App not configured or GitHub unreachable
            note += f"; comment not posted ({type(exc).__name__})"
        _finish(repo, read, output=note)
        repo.update_status(run_id, RunStatus.could_not_reproduce)
        return
    _finish(repo, read, output=run.issue_title)

    repo.update_status(run_id, RunStatus.reproducing)
    reproduce = _start(repo, run_id, PipelineStep.reproduce)
    result, _ = await clone_and_test_async(
        repository_url(run.repository_full_name),
        SandboxConfig(),
        container_name(run.issue_number),
    )
    if result.environment_error or result.timed_out:
        _finish(repo, reproduce, error=result.message())
        repo.update_status(run_id, RunStatus.failed)
        return
    output = (result.stdout or result.stderr)[-MAX_OUTPUT_CHARS:]
    _finish(repo, reproduce, output=f"baseline suite: {result.message()}\n{output}")

    diagnose = _start(repo, run_id, PipelineStep.diagnose)
    _finish(repo, diagnose, error=NOT_AVAILABLE)
    repo.update_status(run_id, RunStatus.failed, test_output=output)
