"""In-process run queue used by the API process.

The queue owns scheduling only. Routes (and the GitHub webhook) call the
synchronous `enqueue(run_id)`; a bounded number of asyncio tasks then run the
registered handler on the API event loop.

The handler is supplied by the pipeline package. It is discovered from
``pipeline.runner.handle_run(run_id: UUID) -> Awaitable[None]`` at startup, so
the API and the pipeline stay decoupled: the pipeline can land its runner
without editing this module, and the API keeps accepting webhooks (logging a
warning) until that module exists.

Failures inside a handler are logged and never propagate to the request that
enqueued the run; run state is the pipeline's contract, not the queue's.
"""
from __future__ import annotations

import asyncio
import importlib
import logging
from collections.abc import Awaitable, Callable
from typing import cast
from uuid import UUID

logger = logging.getLogger(__name__)

RunHandler = Callable[[UUID], Awaitable[None]]
ErrorHandler = Callable[[UUID, BaseException], Awaitable[None] | None]
HANDLER_MODULE = "pipeline.runner"
HANDLER_NAME = "handle_run"


def load_handler() -> RunHandler | None:
    """Return ``pipeline.runner.handle_run`` when the module exists."""
    try:
        module = importlib.import_module(HANDLER_MODULE)
    except ImportError:
        return None
    handler = getattr(module, HANDLER_NAME, None)
    if callable(handler):
        return cast(RunHandler, handler)
    return None


class PipelineQueue:
    """Bounded, in-process asyncio queue for pipeline runs."""

    def __init__(
        self,
        handler: RunHandler | None = None,
        *,
        concurrency: int = 2,
        on_error: ErrorHandler | None = None,
    ) -> None:
        self._handler = handler
        self._concurrency = max(1, concurrency)
        self._on_error = on_error
        self._tasks: set[asyncio.Task[None]] = set()
        self._semaphore: asyncio.Semaphore | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def handler(self) -> RunHandler | None:
        return self._handler

    def set_handler(self, handler: RunHandler | None) -> None:
        self._handler = handler

    def set_error_handler(self, on_error: ErrorHandler | None) -> None:
        self._on_error = on_error

    def enqueue(self, run_id: UUID) -> bool:
        """Schedule `run_id`; returns False when no handler is registered.

        Called from async request handlers. A synchronous caller (for example a
        script) falls back to running the handler to completion in a new loop.
        """
        if self._handler is None:
            logger.warning("no pipeline handler registered; run %s stays pending", run_id)
            return False
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self._process(run_id))
            return True
        task = loop.create_task(self._process(run_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return True

    def _semaphore_for(self, loop: asyncio.AbstractEventLoop) -> asyncio.Semaphore:
        if self._semaphore is None or self._loop is not loop:
            self._semaphore = asyncio.Semaphore(self._concurrency)
            self._loop = loop
        return self._semaphore

    async def _process(self, run_id: UUID) -> None:
        handler = self._handler
        if handler is None:
            return
        semaphore = self._semaphore_for(asyncio.get_running_loop())
        async with semaphore:
            try:
                await handler(run_id)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("pipeline handler failed for run %s", run_id)
                await self._report_failure(run_id, exc)

    async def _report_failure(self, run_id: UUID, exc: BaseException) -> None:
        """Tell the owner of the queue that a run failed, without re-raising."""
        if self._on_error is None:
            return
        try:
            result = self._on_error(run_id, exc)
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            logger.exception("pipeline error handler failed for run %s", run_id)

    async def wait(self) -> None:
        """Wait until every scheduled run has finished (tests, shutdown)."""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def shutdown(self) -> None:
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()


def enqueue_run(queue: object, run_id: UUID) -> bool:
    """Enqueue through a `PipelineQueue` or a legacy bare callable."""
    if queue is None:
        return False
    method = getattr(queue, "enqueue", None)
    if callable(method):
        return bool(method(run_id))
    if callable(queue):
        queue(run_id)
        return True
    logger.warning("pipeline queue %r cannot be called; run %s stays pending", queue, run_id)
    return False
