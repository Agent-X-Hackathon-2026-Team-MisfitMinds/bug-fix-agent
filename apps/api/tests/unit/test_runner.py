"""`pipeline.runner.handle_run` must load, read the real run and end honestly."""
import asyncio
from typing import Any, cast

import pytest

from data.run_repo import RunRepo
from main import app
from pipeline import runner
from pipeline.queue import load_handler
from pipeline.sandbox import SandboxResult
from schemas import PipelineStep, Run, RunStatus, StepStatus

DETAILED_BODY = (
    "Steps to reproduce: call calculate_discount(100, 20). "
    "Expected behaviour: returns 80. Actual behaviour: returns 81."
)


@pytest.fixture
def repo() -> RunRepo:
    return cast(RunRepo, app.state.run_repo)


def make_run(repo: RunRepo, body: str) -> Run:
    return repo.create(
        installation_id=123,
        repository_full_name="fixie-demo/seeded-repo",
        issue_number=1,
        issue_title="calculate_discount returns 1 more than the discounted price",
        issue_body=body,
        triggered_by="alice",
    )


def fake_sandbox(monkeypatch: pytest.MonkeyPatch, result: SandboxResult) -> list[str]:
    urls: list[str] = []

    async def clone_and_test(url: str, *_: Any, **__: Any) -> tuple[SandboxResult, bool]:
        urls.append(url)
        return result, result.ok

    monkeypatch.setattr(runner, "clone_and_test_async", clone_and_test)
    return urls


def test_queue_discovers_the_handler() -> None:
    assert load_handler() is runner.handle_run


def test_thin_issue_ends_as_could_not_reproduce_and_comments(
    repo: RunRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    comments: list[tuple[int, str, int, str]] = []

    class FakeClient:
        def __init__(self, installation_id: int, repository: str) -> None:
            self.where = (installation_id, repository)

        async def add_issue_comment(self, number: int, body: str) -> dict[str, Any]:
            comments.append((number, body, *self.where))
            return {}

    monkeypatch.setattr(runner, "client_for", FakeClient)
    urls = fake_sandbox(monkeypatch, SandboxResult(0, "", ""))
    run = make_run(repo, "It crashes for some users. Please fix.")

    asyncio.run(runner.handle_run(run.id))

    assert repo.get_by_id(run.id).status is RunStatus.could_not_reproduce
    assert comments == [(1, runner.NEED_MORE_INFO, 123, "fixie-demo/seeded-repo")]
    assert urls == []  # nothing is cloned for an issue that cannot be reproduced
    steps = repo.get_steps_by_id(run.id)
    assert [(s.step, s.status) for s in steps] == [(PipelineStep.read, StepStatus.completed)]
    assert "comment posted" in (steps[0].output or "")


def test_thin_issue_still_ends_honestly_when_the_comment_cannot_be_posted(
    repo: RunRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_app(*_: Any) -> Any:
        raise RuntimeError("GitHub App credentials are not configured")

    monkeypatch.setattr(runner, "client_for", no_app)
    run = make_run(repo, "broken")

    asyncio.run(runner.handle_run(run.id))

    assert repo.get_by_id(run.id).status is RunStatus.could_not_reproduce
    assert "comment not posted (RuntimeError)" in (repo.get_steps_by_id(run.id)[0].output or "")


def test_green_baseline_stops_at_diagnose_without_inventing_a_result(
    repo: RunRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    urls = fake_sandbox(monkeypatch, SandboxResult(0, "7 passed in 0.04s", ""))
    run = make_run(repo, DETAILED_BODY)

    asyncio.run(runner.handle_run(run.id))

    stored = repo.get_by_id(run.id)
    assert stored.status is RunStatus.failed
    assert stored.pr_url is None
    assert stored.test_output == "7 passed in 0.04s"
    assert urls == ["https://github.com/fixie-demo/seeded-repo.git"]
    steps = repo.get_steps_by_id(run.id)
    assert [(s.step, s.status) for s in steps] == [
        (PipelineStep.read, StepStatus.completed),
        (PipelineStep.reproduce, StepStatus.completed),
        (PipelineStep.diagnose, StepStatus.failed),
    ]
    assert steps[2].error == runner.NOT_AVAILABLE


def test_sandbox_environment_error_fails_the_run_at_reproduce(
    repo: RunRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_sandbox(monkeypatch, SandboxResult(125, "", "docker missing", environment_error=True))
    run = make_run(repo, DETAILED_BODY)

    asyncio.run(runner.handle_run(run.id))

    assert repo.get_by_id(run.id).status is RunStatus.failed
    steps = repo.get_steps_by_id(run.id)
    assert steps[-1].step is PipelineStep.reproduce
    assert steps[-1].status is StepStatus.failed
    assert steps[-1].error == "reproduction failed - environment issue"
