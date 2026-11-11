import asyncio
from uuid import UUID, uuid4

import pytest

from pipeline.queue import PipelineQueue, enqueue_run


async def record(calls: list[UUID], run_id: UUID) -> None:
    calls.append(run_id)


def test_enqueue_without_handler_returns_false(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("WARNING"):
        assert PipelineQueue().enqueue(uuid4()) is False

    assert "stays pending" in caplog.text


def test_enqueue_runs_the_registered_handler() -> None:
    calls: list[UUID] = []

    async def scenario() -> UUID:
        queue = PipelineQueue()
        queue.set_handler(lambda run_id: record(calls, run_id))
        run_id = uuid4()
        assert queue.enqueue(run_id) is True
        await queue.wait()
        return run_id

    run_id = asyncio.run(scenario())

    assert calls == [run_id]


def test_handler_failure_is_logged_and_does_not_propagate(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def handler(run_id: UUID) -> None:
        raise RuntimeError("boom")

    async def scenario() -> None:
        queue = PipelineQueue(handler)
        assert queue.enqueue(uuid4())
        await queue.wait()

    with caplog.at_level("ERROR"):
        asyncio.run(scenario())

    assert "pipeline handler failed" in caplog.text


def test_shutdown_cancels_in_flight_runs() -> None:
    cancelled: list[bool] = []

    async def handler(run_id: UUID) -> None:
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    async def scenario() -> None:
        queue = PipelineQueue(handler)
        queue.enqueue(uuid4())
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        await queue.shutdown()

    asyncio.run(scenario())

    assert cancelled == [True]


def test_enqueue_run_accepts_pipeline_queue() -> None:
    calls: list[UUID] = []

    async def scenario() -> None:
        queue = PipelineQueue()
        queue.set_handler(lambda run_id: record(calls, run_id))
        run_id = uuid4()
        assert enqueue_run(queue, run_id) is True
        await queue.wait()
        assert calls == [run_id]

    asyncio.run(scenario())


def test_enqueue_run_accepts_a_legacy_callable() -> None:
    calls: list[UUID] = []
    run_id = uuid4()

    assert enqueue_run(calls.append, run_id) is True
    assert calls == [run_id]


def test_enqueue_run_ignores_a_missing_queue() -> None:
    assert enqueue_run(None, uuid4()) is False
