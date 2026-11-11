"""Prove the seam between the queue, RunRepo and the SSE stream.

The pipeline's node logic lives in `pipeline.langgraph` (Durgesh); this test
replaces it with a stub handler that writes the same run state and asserts the
exact events the dashboard subscribes to (`step_updated`,
`run_status_changed`) and the `pr_url` the PR link needs.
"""
from typing import cast
from uuid import UUID

import json

from fastapi.testclient import TestClient

from auth.deps import SESSION_COOKIE
from data.run_repo import RunRepo
from main import app
from pipeline.queue import PipelineQueue
from schemas import PipelineStep, Run, RunStatus, RunStep, StepStatus

client = TestClient(app)
PR_URL = "https://github.com/fixie-demo/seeded-repo/pull/12"


def login() -> str:
    session = app.state.sessions.create(
        github_user_id=1,
        github_login="alice",
        encrypted_token="encrypted",
        installation_id=123,
    )
    return str(session.id)


def make_run(repo: RunRepo) -> Run:
    return repo.create(
        installation_id=123,
        repository_full_name="fixie-demo/seeded-repo",
        issue_number=4,
        issue_title="Discount off by one",
        issue_body="100 at 10% returns 91",
        triggered_by="alice",
    )


def stub_pipeline(repo: RunRepo) -> PipelineQueue:
    """Stand-in for `pipeline.runner.handle_run`, writing the same contract."""

    async def handle_run(run_id: UUID) -> None:
        repo.update_status(run_id, RunStatus.reproducing)
        step = RunStep(run_id=run_id, step=PipelineStep.reproduce, status=StepStatus.running)
        repo.add_step(step)
        repo.update_step(
            step.model_copy(update={"status": StepStatus.completed, "output": "1 failed"})
        )
        repo.update_status(
            run_id,
            RunStatus.completed,
            pr_url=PR_URL,
            pr_number=12,
            test_output="7 passed",
        )

    return PipelineQueue(handle_run)


def stream_events(session_id: str, run_id: UUID) -> str:
    with client.stream(
        "GET", f"/runs/{run_id}/events", cookies={SESSION_COOKIE: session_id}
    ) as response:
        assert response.status_code == 200
        return "\n".join(line for line in response.iter_lines() if line)


def test_a_queued_run_reaches_the_dashboard_as_completed_with_a_pr_link() -> None:
    repo = cast(RunRepo, app.state.run_repo)
    run = make_run(repo)

    # A synchronous caller runs the handler to completion, which is what the
    # webhook path does inside the event loop.
    assert stub_pipeline(repo).enqueue(run.id) is True

    stored = repo.get_by_id(run.id)
    assert stored.status is RunStatus.completed
    assert stored.pr_url == PR_URL
    assert stored.test_output == "7 passed"
    assert [step.status for step in repo.get_steps_by_id(run.id)] == [StepStatus.completed]

    joined = stream_events(login(), run.id)

    assert "event: run_status_changed" in joined
    assert "event: step_updated" in joined

    payloads = [
        json.loads(line[len("data: "):])
        for line in joined.splitlines()
        if line.startswith("data: ")
    ]
    assert [event["status"] for event in payloads if "step" not in event] == ["completed"]
    assert [event["step"] for event in payloads if "step" in event] == ["reproduce"]


def test_the_detail_endpoint_shows_steps_and_the_pr_url() -> None:
    repo = cast(RunRepo, app.state.run_repo)
    run = make_run(repo)
    assert stub_pipeline(repo).enqueue(run.id) is True

    response = client.get(f"/runs/{run.id}", cookies={SESSION_COOKIE: login()})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["pr_url"] == PR_URL
    assert [step["step"] for step in body["steps"]] == ["reproduce"]
    assert body["steps"][0]["status"] == "completed"
