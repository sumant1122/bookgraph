from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


class AgentScheduler:
    """
    Minimal periodic scheduler for long-running FastAPI processes.
    """

    def __init__(self) -> None:
        self._tasks: list[asyncio.Task] = []
        self._running = False

    def start(self, jobs: list[tuple[str, int, Callable[[], None]]]) -> None:
        if self._running:
            return
        self._running = True
        for name, interval_seconds, job in jobs:
            task = asyncio.create_task(self._run_loop(name, interval_seconds, job))
            self._tasks.append(task)

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def _run_loop(self, name: str, interval_seconds: int, job: Callable[[], None]) -> None:
        while self._running:
            try:
                await asyncio.to_thread(job)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Scheduled agent '%s' failed: %s", name, exc)
            await asyncio.sleep(max(30, interval_seconds))
