# Worker guard errors intentionally state the violated bounded-loop invariant.
# ruff: noqa: TRY003

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime, timezone


class ResearchWorker:
    def __init__(
        self,
        kernel,
        workflow,
        *,
        next_run: Callable[[], str | None],
        poll_seconds: float = 1.0,
        reclaim_seconds: float = 30.0,
        concurrency: int = 1,
    ) -> None:
        self.kernel = kernel
        self.workflow = workflow
        self.next_run_id = next_run
        self.poll_seconds = poll_seconds
        self.reclaim_seconds = reclaim_seconds
        self.concurrency = concurrency
        self.stop_event = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []

    def _next_run(self) -> str | None:
        try:
            return self.next_run_id()
        except StopIteration:
            return None

    async def run_next(self) -> bool:
        run_id = self._next_run()
        if run_id is None:
            return False
        try:
            return bool(await self.workflow.run_next(run_id))
        except Exception:
            # ResearchWorkflow checkpoints ordinary failures before returning. A crash
            # leaves its lease durable for periodic/startup reclamation.
            return False

    async def run_until_idle(self, *, max_iterations: int = 10_000) -> int:
        completed = 0
        for _iteration in range(max_iterations):
            run_id = self._next_run()
            if run_id is None:
                return completed
            try:
                completed += bool(await self.workflow.run_next(run_id))
            except Exception:
                continue
        raise RuntimeError("worker did not become idle")

    async def _loop(self) -> None:
        loop = asyncio.get_running_loop()
        last_reclaim = loop.time()
        while not self.stop_event.is_set():
            if loop.time() - last_reclaim >= self.reclaim_seconds:
                self.kernel.reconcile_startup(datetime.now(timezone.utc))
                last_reclaim = loop.time()
            worked = await self.run_next()
            if not worked:
                with suppress(TimeoutError):
                    await asyncio.wait_for(
                        self.stop_event.wait(), timeout=max(self.poll_seconds, 0.001)
                    )

    async def run(self) -> None:
        self.stop_event.clear()
        self._tasks = [
            asyncio.create_task(self._loop(), name=f"research-worker-{index}")
            for index in range(self.concurrency)
        ]
        await asyncio.gather(*self._tasks)

    def start(self) -> None:
        if not self._tasks:
            self._tasks = [asyncio.create_task(self.run(), name="research-worker")]

    async def stop(self) -> None:
        self.stop_event.set()
        tasks = tuple(self._tasks)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
