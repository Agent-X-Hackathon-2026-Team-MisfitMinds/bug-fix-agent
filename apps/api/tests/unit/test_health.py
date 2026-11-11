from uuid import UUID

from fastapi.testclient import TestClient

from main import app
from pipeline.queue import PipelineQueue


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "pipeline": "no-handler"}


def test_health_reports_ready_when_a_handler_is_registered() -> None:
    async def handler(run_id: UUID) -> None:
        return None

    app.state.pipeline_queue = PipelineQueue(handler)

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "pipeline": "ready"}
