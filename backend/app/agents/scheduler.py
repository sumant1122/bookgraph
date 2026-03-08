from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from typing import Protocol

logger = logging.getLogger(__name__)


class AgentJobStateStore(Protocol):
    def try_acquire_agent_job(self, name: str, owner_id: str, lease_seconds: int) -> bool:
        ...

    def complete_agent_job_run(self, name: str, owner_id: str, status: str, error: str | None = None) -> None:
        ...


class AgentScheduler:
    """
    Periodic scheduler with ownership locking and persisted job state.
    """

    def __init__(
        self,
        *,
        owner_id: str | None = None,
        state_store: AgentJobStateStore | None = None,
    ) -> None:
        self._owner_id = owner_id or str(uuid.uuid4())
        self._state_store = state_store
        self._tasks: list[asyncio.Task] = []
        self._running = False
        self._local_running_jobs: set[str] = set()

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
            if name in self._local_running_jobs:
                await asyncio.sleep(1)
                continue

            lease_seconds = max(300, interval_seconds * 2)
            acquired = True
            if self._state_store:
                acquired = await asyncio.to_thread(
                    self._state_store.try_acquire_agent_job,
                    name,
                    self._owner_id,
                    lease_seconds,
                )

            if not acquired:
                await asyncio.sleep(min(interval_seconds, 60))
                continue

            self._local_running_jobs.add(name)
            status = "idle"
            error: str | None = None
            try:
                await asyncio.to_thread(job)
            except Exception as exc:  # noqa: BLE001
                status = "error"
                error = str(exc)[:500]
                logger.exception("Scheduled agent '%s' failed: %s", name, exc)
            finally:
                self._local_running_jobs.discard(name)
                if self._state_store:
                    await asyncio.to_thread(
                        self._state_store.complete_agent_job_run,
                        name,
                        self._owner_id,
                        status,
                        error,
                    )
            await asyncio.sleep(max(30, interval_seconds))
