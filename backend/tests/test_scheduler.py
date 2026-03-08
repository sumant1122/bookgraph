from __future__ import annotations

import asyncio
import threading
import unittest

from app.agents.scheduler import AgentScheduler


class FakeStateStore:
    def __init__(self, acquire: bool = True) -> None:
        self.acquire = acquire
        self.try_calls: list[tuple[str, str, int]] = []
        self.complete_calls: list[tuple[str, str, str, str | None]] = []

    def try_acquire_agent_job(self, name: str, owner_id: str, lease_seconds: int) -> bool:
        self.try_calls.append((name, owner_id, lease_seconds))
        return self.acquire

    def complete_agent_job_run(self, name: str, owner_id: str, status: str, error: str | None = None) -> None:
        self.complete_calls.append((name, owner_id, status, error))


class SchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def _wait_for(self, predicate, timeout_seconds: float = 1.0) -> None:  # noqa: ANN001
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            if predicate():
                return
            await asyncio.sleep(0.01)
        self.fail("timed out waiting for predicate")

    async def test_runs_job_and_records_idle_status(self) -> None:
        state = FakeStateStore(acquire=True)
        ran = threading.Event()

        def job() -> None:
            ran.set()

        scheduler = AgentScheduler(owner_id="owner-a", state_store=state)
        scheduler.start([("graph_explorer", 1, job)])
        await self._wait_for(lambda: ran.is_set())
        await self._wait_for(lambda: len(state.complete_calls) >= 1)
        await scheduler.stop()

        self.assertGreaterEqual(len(state.try_calls), 1)
        self.assertEqual(state.complete_calls[0][2], "idle")
        self.assertIsNone(state.complete_calls[0][3])

    async def test_skips_job_when_lock_not_acquired(self) -> None:
        state = FakeStateStore(acquire=False)
        calls = {"count": 0}

        def job() -> None:
            calls["count"] += 1

        scheduler = AgentScheduler(owner_id="owner-b", state_store=state)
        scheduler.start([("graph_explorer", 1, job)])
        await asyncio.sleep(0.05)
        await scheduler.stop()

        self.assertEqual(calls["count"], 0)
        self.assertGreaterEqual(len(state.try_calls), 1)
        self.assertEqual(len(state.complete_calls), 0)

    async def test_records_error_status_when_job_fails(self) -> None:
        state = FakeStateStore(acquire=True)

        def job() -> None:
            raise RuntimeError("boom")

        scheduler = AgentScheduler(owner_id="owner-c", state_store=state)
        scheduler.start([("graph_explorer", 1, job)])
        await self._wait_for(lambda: len(state.complete_calls) >= 1)
        await scheduler.stop()

        self.assertEqual(state.complete_calls[0][2], "error")
        self.assertIn("boom", state.complete_calls[0][3] or "")
