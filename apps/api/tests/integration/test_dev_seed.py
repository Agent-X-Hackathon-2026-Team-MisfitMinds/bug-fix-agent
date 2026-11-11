"""Integration tests for the dev-only seed endpoint."""
from fastapi.testclient import TestClient

from auth.deps import SESSION_COOKIE
from main import app

client = TestClient(app)


def login(login: str, installation_id: int = 1) -> dict[str, str]:
    session = app.state.sessions.create(
        github_user_id=1,
        github_login=login,
        encrypted_token="encrypted",
        installation_id=installation_id,
    )
    return {SESSION_COOKIE: str(session.id)}


def test_seed_runs_requires_auth() -> None:
    response = client.post("/dev/seed-runs")
    assert response.status_code == 401


def test_seed_runs_creates_one_run_per_status() -> None:
    cookies = login("seeder1")
    response = client.post("/dev/seed-runs", cookies=cookies)
    assert response.status_code == 200
    statuses = {run["status"] for run in response.json()["data"]}
    assert statuses == {"completed", "failed", "could_not_reproduce", "pending"}


def test_seeded_runs_visible_in_list_and_detail() -> None:
    cookies = login("seeder2")
    client.post("/dev/seed-runs", cookies=cookies)
    listed = client.get("/runs", cookies=cookies).json()["data"]
    assert len(listed) == 4
    run_id = listed[0]["id"]
    detail = client.get(f"/runs/{run_id}", cookies=cookies)
    assert detail.status_code == 200
    assert len(detail.json()["steps"]) >= 1


def test_seeded_runs_isolated_per_user() -> None:
    cookies_a = login("seeder3a")
    cookies_b = login("seeder3b")
    client.post("/dev/seed-runs", cookies=cookies_a)
    assert client.get("/runs", cookies=cookies_b).json()["data"] == []


def test_seeded_failed_run_is_retryable() -> None:
    cookies = login("seeder4")
    client.post("/dev/seed-runs", cookies=cookies)
    failed = client.get("/runs?status=failed", cookies=cookies).json()["data"]
    assert len(failed) == 1
    response = client.post(
        f"/runs/{failed[0]['id']}/retry",
        headers={"Idempotency-Key": "seed-retry-1"},
        cookies=cookies,
    )
    assert response.status_code == 200
    after = client.get(f"/runs/{failed[0]['id']}", cookies=cookies).json()
    assert after["status"] == "pending"
    assert after["steps"] == []
