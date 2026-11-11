from uuid import UUID

from fastapi.testclient import TestClient

from auth.deps import SESSION_COOKIE
from data.run_repo import RunRepo
from main import app
from schemas import PipelineStep, Run, RunStatus, RunStep, StepStatus

client = TestClient(app)


class QueueSpy:
    def __init__(self) -> None:
        self.run_ids: list[UUID] = []

    def enqueue(self, run_id: UUID) -> bool:
        self.run_ids.append(run_id)
        return True


def login(login: str = "alice", installation_id: int = 1) -> str:
    session = app.state.sessions.create(
        github_user_id=1,
        github_login=login,
        encrypted_token="encrypted",
        installation_id=installation_id,
    )
    return str(session.id)


def create_run(
    *,
    login: str = "alice",
    installation_id: int = 1,
    issue_number: int = 1,
    status: RunStatus = RunStatus.pending,
) -> Run:
    repo: RunRepo = app.state.run_repo
    run = repo.create(
        installation_id=installation_id,
        repository_full_name="fixie-demo/seeded-repo",
        issue_number=issue_number,
        issue_title="t",
        issue_body="b",
        triggered_by=login,
    )
    if status != RunStatus.pending:
        return repo.update_status(run.id, status)
    return run


def add_step(run: Run, step: PipelineStep = PipelineStep.read) -> None:
    app.state.run_repo.add_step(
        RunStep(run_id=run.id, step=step, status=StepStatus.completed, output="ok")
    )


def test_unauthenticated_list_returns_401() -> None:
    response = client.get("/runs")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_list_only_returns_own_runs() -> None:
    session_id = login()
    create_run(issue_number=1)
    create_run(issue_number=2)
    create_run(login="bob", issue_number=3)

    response = client.get("/runs", cookies={SESSION_COOKIE: session_id})
    assert response.status_code == 200
    body = response.json()
    assert {item["issue_number"] for item in body["data"]} == {1, 2}
    assert body["has_more"] is False
    assert body["next_cursor"] is None


def test_list_filters_by_status_and_paginates() -> None:
    session_id = login()
    create_run(issue_number=1, status=RunStatus.failed)
    create_run(issue_number=2)
    create_run(issue_number=3)

    response = client.get(
        "/runs",
        params={"limit": 1, "status": "failed"},
        cookies={SESSION_COOKIE: session_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["status"] == "failed"


def test_list_rejects_invalid_query_params() -> None:
    session_id = login()
    cases: list[dict[str, int | str]] = [
        {"limit": 0},
        {"limit": 101},
        {"status": "bogus"},
    ]
    for params in cases:
        response = client.get("/runs", params=params, cookies={SESSION_COOKIE: session_id})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_foreign_run_returns_404_not_403() -> None:
    session_id = login()
    foreign = create_run(login="bob")
    other_installation = create_run(login="alice", installation_id=99)

    for run_id in (foreign.id, other_installation.id):
        response = client.get(f"/runs/{run_id}", cookies={SESSION_COOKIE: session_id})
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"


def test_run_detail_includes_steps() -> None:
    session_id = login()
    run = create_run(status=RunStatus.completed)
    add_step(run)

    response = client.get(f"/runs/{run.id}", cookies={SESSION_COOKIE: session_id})
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(run.id)
    assert body["status"] == "completed"
    assert body["steps"][0]["step"] == "read"
    assert body["steps"][0]["output"] == "ok"


def test_sse_streams_status_and_steps_for_terminal_run() -> None:
    session_id = login()
    run = create_run(status=RunStatus.completed)
    add_step(run)

    with client.stream("GET", f"/runs/{run.id}/events",
                       cookies={SESSION_COOKIE: session_id}) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        lines = [line for line in response.iter_lines() if line]

    assert "event: run_status_changed" in lines
    assert "event: step_updated" in lines


def test_retry_requires_idempotency_key() -> None:
    session_id = login()
    run = create_run(status=RunStatus.failed)
    response = client.post(f"/runs/{run.id}/retry", cookies={SESSION_COOKIE: session_id})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_retry_only_retryable_states() -> None:
    session_id = login()
    run = create_run(status=RunStatus.pending)
    response = client.post(
        f"/runs/{run.id}/retry",
        headers={"Idempotency-Key": "key-1"},
        cookies={SESSION_COOKIE: session_id},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


def test_retry_is_idempotent_and_scoped_to_run() -> None:
    session_id = login()
    failed = create_run(issue_number=1, status=RunStatus.failed)
    other = create_run(issue_number=2, status=RunStatus.failed)
    headers = {"Idempotency-Key": "key-replay"}

    first = client.post(f"/runs/{failed.id}/retry", headers=headers,
                        cookies={SESSION_COOKIE: session_id})
    replay = client.post(f"/runs/{failed.id}/retry", headers=headers,
                         cookies={SESSION_COOKIE: session_id})
    conflict = client.post(f"/runs/{other.id}/retry", headers=headers,
                           cookies={SESSION_COOKIE: session_id})

    assert first.status_code == 200
    assert first.json() == {"status": "retry_queued", "run_id": str(failed.id)}
    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert conflict.status_code == 409


def test_retry_reenqueues_the_run() -> None:
    session_id = login()
    run = create_run(status=RunStatus.failed)
    spy = QueueSpy()
    app.state.pipeline_queue = spy

    response = client.post(
        f"/runs/{run.id}/retry",
        headers={"Idempotency-Key": "key-requeue"},
        cookies={SESSION_COOKIE: session_id},
    )

    assert response.status_code == 200
    assert spy.run_ids == [run.id]


def test_list_rate_limit_returns_429() -> None:
    session_id = login()
    for _ in range(60):
        assert client.get("/runs", cookies={SESSION_COOKIE: session_id}).status_code == 200

    response = client.get("/runs", cookies={SESSION_COOKIE: session_id})
    assert response.status_code == 429
    assert response.headers["Retry-After"]
    assert response.json()["error"]["code"] == "RATE_LIMITED"


def test_retry_rate_limit_returns_429() -> None:
    session_id = login()
    run = create_run(status=RunStatus.pending)
    for index in range(5):
        response = client.post(
            f"/runs/{run.id}/retry",
            headers={"Idempotency-Key": f"limit-key-{index}"},
            cookies={SESSION_COOKIE: session_id},
        )
        assert response.status_code == 409

    response = client.post(
        f"/runs/{run.id}/retry",
        headers={"Idempotency-Key": "limit-key-final"},
        cookies={SESSION_COOKIE: session_id},
    )
    assert response.status_code == 429


def test_invalid_run_id_returns_400() -> None:
    session_id = login()
    response = client.get("/runs/not-a-uuid", cookies={SESSION_COOKIE: session_id})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
