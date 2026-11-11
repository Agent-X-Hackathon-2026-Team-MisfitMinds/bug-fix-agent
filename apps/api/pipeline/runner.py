"""Pipeline runner entry point discovered by main.py at startup.

The runner owns the end-to-end loop: clone once, prove a reproduction test is
red, diagnose, patch, prove it is green without breaking the existing suite,
then open a draft PR. Every step and status change is persisted to ``RunRepo``
so the dashboard's SSE stream reflects real work rather than placeholders.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from data.run_repo import RunRepo
from errors import NotFoundError
from main import app
from pipeline import langgraph
from pipeline.github_client import client_for
from pipeline.llm import LLMWrapper, default_llm
from pipeline.pytest_runner import PytestRunner
from pipeline.sandbox import prepare_workspace, repository_url
from schemas import (
    ConfidenceLevel,
    PipelineStep,
    Run,
    RunState,
    RunStatus,
    RunStep,
    StepStatus,
)

logger = logging.getLogger(__name__)

NEED_MORE_INFO = langgraph.NEED_MORE_INFO
COULD_NOT_REPRODUCE = (
    "I could not reproduce this: the test written from the report passes on the "
    "current code, so no change was made and no pull request was opened."
)
MAX_PATCH_ATTEMPTS = 3
MAX_STEP_OUTPUT = 4_000
MAX_RUN_OUTPUT = 10_000


def _repo() -> RunRepo:
    return cast(RunRepo, app.state.run_repo)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]"


def _last_error(state: RunState) -> str:
    return state.errors[-1] if state.errors else "pipeline step failed"


def _evidence_fields(state: RunState) -> dict[str, Any]:
    output = state.after_test_output or state.before_output or state.before_test_output
    fields: dict[str, Any] = {}
    if output:
        fields["test_output"] = _clip(output, MAX_RUN_OUTPUT)
    if state.root_cause:
        fields["root_cause"] = state.root_cause
    return fields


class _StepTracker:
    """Create and update persisted step rows for one run."""

    def __init__(self, repo: RunRepo, run_id: UUID) -> None:
        self.repo = repo
        self.run_id = run_id

    def start(self, step: PipelineStep, output: str | None = None) -> RunStep:
        row = RunStep(
            run_id=self.run_id,
            step=step,
            status=StepStatus.running,
            started_at=_now(),
            output=_clip(output, MAX_STEP_OUTPUT) if output else None,
        )
        self.repo.add_step(row)
        return row

    def update(self, row: RunStep, output: str) -> RunStep:
        updated = row.model_copy(update={"output": _clip(output, MAX_STEP_OUTPUT)})
        self.repo.update_step(updated)
        return updated

    def complete(self, row: RunStep, output: str | None = None) -> RunStep:
        updates: dict[str, Any] = {
            "status": StepStatus.completed,
            "completed_at": _now(),
        }
        if output is not None:
            updates["output"] = _clip(output, MAX_STEP_OUTPUT)
        updated = row.model_copy(update=updates)
        self.repo.update_step(updated)
        return updated

    def fail(self, row: RunStep, error: str) -> RunStep:
        updated = row.model_copy(
            update={
                "status": StepStatus.failed,
                "completed_at": _now(),
                "error": _clip(error, MAX_STEP_OUTPUT),
            }
        )
        self.repo.update_step(updated)
        return updated


async def _comment(run: Run, body: str) -> str:
    """Post an issue comment; a failed comment never changes the run outcome."""
    try:
        client = client_for(run.installation_id, run.repository_full_name)
        await client.add_issue_comment(run.issue_number, body)
        return "comment posted"
    except Exception as exc:
        return f"comment not posted ({type(exc).__name__})"


async def _post_need_more_info(run: Run) -> str:
    return "issue fetched; " + await _comment(run, NEED_MORE_INFO)


async def handle_run(run_id: UUID) -> None:
    repo = _repo()
    try:
        run = repo.get_by_id(run_id)
    except NotFoundError:
        return

    state = RunState(
        run_id=str(run.id),
        issue_id=run.issue_number,
        repo_name=run.repository_full_name,
        issue_title=run.issue_title,
        issue_body=run.issue_body,
    )
    steps = _StepTracker(repo, run.id)
    active: RunStep | None = None
    workspace: Path | None = None

    try:
        active = steps.start(PipelineStep.read)
        state = await langgraph.read_node(state)

        if state.status is RunStatus.failed:
            steps.fail(active, _last_error(state))
            repo.update_status(run.id, RunStatus.failed)
            return
        if state.status is RunStatus.could_not_reproduce:
            output = await _post_need_more_info(run)
            steps.complete(active, output=output)
            repo.update_status(run.id, RunStatus.could_not_reproduce)
            return

        steps.complete(active, output="issue fetched; reproduction steps found")
        active = None
        repo.update_status(run.id, RunStatus.reproducing)

        active = steps.start(PipelineStep.reproduce)
        try:
            workspace = await asyncio.to_thread(
                prepare_workspace,
                repository_url(run.repository_full_name),
            )
        except Exception as exc:
            steps.fail(active, f"workspace clone failed: {exc}")
            repo.update_status(run.id, RunStatus.failed)
            return

        llm = LLMWrapper(cache=default_llm.cache)
        pytest_runner = PytestRunner(
            workspace=workspace,
            timeout=300,
            issue_id=run.issue_number,
        )
        state = await langgraph.reproduce_node(state, workspace, pytest_runner, llm)

        if state.status is RunStatus.failed:
            steps.fail(active, _last_error(state))
            repo.update_status(
                run.id, RunStatus.failed, **_evidence_fields(state)
            )
            return
        if state.status is RunStatus.could_not_reproduce:
            note = await _comment(run, COULD_NOT_REPRODUCE)
            steps.complete(active, output=f"{_last_error(state)}; {note}")
            repo.update_status(
                run.id, RunStatus.could_not_reproduce, **_evidence_fields(state)
            )
            return

        steps.complete(
            active,
            output=(
                "baseline suite green; "
                f"{state.reproduction_test_path} failed as expected"
            ),
        )
        active = None
        repo.update_status(run.id, RunStatus.reproducing, **_evidence_fields(state))

        active = steps.start(PipelineStep.diagnose)
        state = await langgraph.diagnose_node(state, llm, workspace)
        if state.status is RunStatus.failed:
            steps.fail(active, _last_error(state))
            repo.update_status(run.id, RunStatus.failed, **_evidence_fields(state))
            return
        steps.complete(active, output=state.root_cause or "root cause found")
        active = None
        repo.update_status(run.id, RunStatus.fixing, **_evidence_fields(state))

        fix_row = steps.start(PipelineStep.fix)
        verify_row: RunStep | None = None
        attempts = 0
        while attempts < MAX_PATCH_ATTEMPTS:
            attempts += 1
            active = fix_row
            if attempts > 1:
                steps.update(
                    fix_row,
                    output=f"attempt {attempts}: revising patch after failed verification",
                )
            state = await langgraph.fix_node(state, llm, workspace)
            if state.status is RunStatus.failed:
                steps.fail(fix_row, _last_error(state))
                repo.update_status(
                    run.id, RunStatus.failed, **_evidence_fields(state)
                )
                return

            if state.status is RunStatus.fixing:
                steps.update(fix_row, output=f"attempt {attempts}: {_last_error(state)}")
                continue

            description = (state.patch or {}).get("description", "patched")
            steps.update(fix_row, output=f"attempt {attempts}: {description}")
            repo.update_status(run.id, RunStatus.verifying)

            if verify_row is None:
                verify_row = steps.start(PipelineStep.verify)
            else:
                steps.update(
                    verify_row,
                    output=f"attempt {attempts}: re-running verification",
                )
            active = verify_row
            state = await langgraph.verify_node(state, workspace, pytest_runner)

            if state.status is RunStatus.verifying:
                steps.complete(fix_row, output=f"attempt {attempts}: {description}")
                steps.complete(
                    verify_row,
                    output="reproduction test green; full suite green",
                )
                active = None
                break
            if state.status is RunStatus.failed:
                steps.fail(verify_row, _last_error(state))
                steps.fail(fix_row, _last_error(state))
                repo.update_status(
                    run.id, RunStatus.failed, **_evidence_fields(state)
                )
                return

            steps.update(
                verify_row,
                output=f"attempt {attempts} failed; retrying fix",
            )
            repo.update_status(run.id, RunStatus.fixing, **_evidence_fields(state))
        else:
            error = _last_error(state) or "verification failed after maximum attempts"
            if verify_row is not None:
                steps.fail(verify_row, error)
            steps.fail(fix_row, error)
            repo.update_status(run.id, RunStatus.failed, **_evidence_fields(state))
            return

        if attempts == 1:
            confidence = ConfidenceLevel.high
            reasons = [
                "baseline suite was green",
                "reproduction test failed before the patch",
                "reproduction test passed after the patch",
                "full suite stayed green on the first patch",
            ]
        else:
            confidence = ConfidenceLevel.medium
            reasons = [
                "baseline suite was green",
                "reproduction test failed before the patch",
                f"patch verified after {attempts} attempts",
                "full suite stayed green after the final patch",
            ]
        state.confidence = confidence
        state.confidence_reasons = reasons
        repo.update_status(
            run.id,
            RunStatus.verifying,
            confidence=confidence,
            **_evidence_fields(state),
        )

        active = steps.start(PipelineStep.pr)
        try:
            github_client = client_for(run.installation_id, run.repository_full_name)
        except Exception as exc:
            steps.fail(active, f"GitHub client unavailable: {exc}")
            repo.update_status(run.id, RunStatus.failed, **_evidence_fields(state))
            return
        state = await langgraph.pr_node(state, github_client)
        if state.status is not RunStatus.completed or not state.pr_url:
            steps.fail(active, _last_error(state))
            repo.update_status(run.id, RunStatus.failed, **_evidence_fields(state))
            return

        note = await _comment(
            run,
            f"Draft pull request opened: {state.pr_url}\n\n"
            "It contains the fix and a reproduction test. A human must review and merge it.",
        )
        steps.complete(active, output=f"{state.pr_url}; {note}")
        repo.update_status(
            run.id,
            RunStatus.completed,
            pr_url=state.pr_url,
            pr_number=state.pr_number,
            confidence=confidence,
            **_evidence_fields(state),
        )
    except Exception as exc:
        logger.exception("pipeline run %s failed unexpectedly", run_id)
        if active is not None:
            steps.fail(active, f"{type(exc).__name__}: {exc}")
        repo.update_status(run.id, RunStatus.failed)
    finally:
        if workspace is not None:
            await asyncio.to_thread(shutil.rmtree, workspace, True)
