"""The queue watchdog must never leave a run stuck in a non-terminal state."""
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI

from data.run_repo import RunRepo
from main import app, mark_run_failed
from schemas import PipelineStep, Run, RunStatus, RunStep, StepStatus


@pytest.fixture
def repo() -> RunRepo:
    return cast(RunRepo, app.state.run_repo)


def make_run(repo: RunRepo, status: RunStatus = RunStatus.pending) -> Run:
    run = repo.create(
        installation_id=1,
        repository_full_name="fixie-demo/seeded-repo",
        issue_number=7,
        issue_title="Discount off by one",
        issue_body="100 at 10% returns 91",
        triggered_by="alice",
    )
    if status is not RunStatus.pending:
        return repo.update_status(run.id, status)
    return run


def test_failing_handler_marks_the_run_failed(repo: RunRepo) -> None:
    run = make_run(repo)

    mark_run_failed(app, run.id, RuntimeError("sandbox exploded"))

    updated = repo.get_by_id(run.id)
    assert updated.status is RunStatus.failed
    assert updated.completed_at is not None
    steps = repo.get_steps_by_id(run.id)
    assert [step.status for step in steps] == [StepStatus.failed]
    assert steps[0].step is PipelineStep.read
    assert steps[0].error is not None
    assert "RuntimeError: sandbox exploded" in steps[0].error


def test_the_running_step_is_marked_failed_in_place(repo: RunRepo) -> None:
    run = make_run(repo)
    step = RunStep(run_id=run.id, step=PipelineStep.reproduce, status=StepStatus.running)
    repo.add_step(step)

    mark_run_failed(app, run.id, TimeoutError())

    steps = repo.get_steps_by_id(run.id)
    assert len(steps) == 1
    assert steps[0].id == step.id
    assert steps[0].status is StepStatus.failed
    assert steps[0].error == "TimeoutError"
    assert steps[0].completed_at is not None


def test_a_terminal_run_is_not_overwritten(repo: RunRepo) -> None:
    run = make_run(repo, RunStatus.completed)

    mark_run_failed(app, run.id, RuntimeError("late failure"))

    assert repo.get_by_id(run.id).status is RunStatus.completed
    assert repo.get_steps_by_id(run.id) == []


def test_an_unknown_run_is_ignored(repo: RunRepo) -> None:
    mark_run_failed(app, uuid4(), RuntimeError("gone"))


def test_missing_app_state_is_ignored() -> None:
    class Bare:
        class state:  # noqa: N801 - stub of a FastAPI app
            pass

    mark_run_failed(cast(FastAPI, Bare()), uuid4(), RuntimeError("nothing to update"))


def test_error_text_is_truncated(repo: RunRepo) -> None:
    run = make_run(repo)

    mark_run_failed(app, run.id, RuntimeError("x" * 5000))

    error = repo.get_steps_by_id(run.id)[0].error
    assert error is not None
    assert len(error) == 500


def test_watchdog_step_has_a_uuid(repo: RunRepo) -> None:
    run = make_run(repo)

    mark_run_failed(app, run.id, RuntimeError("boom"))

    assert isinstance(repo.get_steps_by_id(run.id)[0].id, UUID)
