import asyncio
from typing import Set

ACTIVE_RUNS: Set[str] = set()
ABORTED_RUNS: Set[str] = set()
RUNS_LOCK = asyncio.Lock()

async def add_active_run(run_id: str):
    async with RUNS_LOCK:
        ACTIVE_RUNS.add(run_id)

async def remove_run(run_id: str):
    async with RUNS_LOCK:
        ACTIVE_RUNS.discard(run_id)
        ABORTED_RUNS.discard(run_id)

async def abort_run(run_id: str):
    async with RUNS_LOCK:
        ABORTED_RUNS.add(run_id)

async def is_aborted(run_id: str) -> bool:
    async with RUNS_LOCK:
        return run_id in ABORTED_RUNS

async def get_active_runs() -> list[str]:
    async with RUNS_LOCK:
        return list(ACTIVE_RUNS)
