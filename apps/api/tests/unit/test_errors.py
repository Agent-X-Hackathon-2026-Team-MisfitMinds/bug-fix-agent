from fastapi import FastAPI
from fastapi.testclient import TestClient

from errors import ConflictError, NotFoundError, RateLimited, register_error_handlers

app = FastAPI()
register_error_handlers(app)


@app.get("/missing")
async def missing() -> None:
    raise NotFoundError("Run not found")


@app.get("/conflict")
async def conflict() -> None:
    raise ConflictError("Duplicate delivery")


@app.get("/limited")
async def limited() -> None:
    raise RateLimited(retry_after=42)


client = TestClient(app)


def test_not_found_uses_standard_error_shape() -> None:
    response = client.get("/missing")
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "NOT_FOUND",
            "message": "Run not found",
            "details": [],
        }
    }


def test_conflict_uses_standard_error_shape() -> None:
    response = client.get("/conflict")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


def test_rate_limited_sets_retry_after() -> None:
    response = client.get("/limited")
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "42"
    assert response.json()["error"]["code"] == "RATE_LIMITED"
