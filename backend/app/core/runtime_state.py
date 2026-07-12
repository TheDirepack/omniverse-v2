import asyncio
from abc import ABC, abstractmethod


class StateManager(ABC):
    @abstractmethod
    async def add_active_run(self, run_id: str):
        pass

    @abstractmethod
    async def remove_run(self, run_id: str):
        pass

    @abstractmethod
    async def abort_run(self, run_id: str):
        pass

    @abstractmethod
    async def is_aborted(self, run_id: str) -> bool:
        pass

    @abstractmethod
    async def get_active_runs(self) -> list[str]:
        pass


class InMemoryStateManager(StateManager):
    def __init__(self):
        self._active_runs: set[str] = set()
        self._aborted_runs: set[str] = set()
        self._lock = asyncio.Lock()

    async def add_active_run(self, run_id: str):
        async with self._lock:
            self._active_runs.add(run_id)

    async def remove_run(self, run_id: str):
        async with self._lock:
            self._active_runs.discard(run_id)
            self._aborted_runs.discard(run_id)

    async def abort_run(self, run_id: str):
        async with self._lock:
            self._aborted_runs.add(run_id)

    async def is_aborted(self, run_id: str) -> bool:
        async with self._lock:
            return run_id in self._aborted_runs

    def is_aborted_sync(self, run_id: str) -> bool:
        return run_id in self._aborted_runs

    async def get_active_runs(self) -> list[str]:
        async with self._lock:
            return list(self._active_runs)


# Singleton instance
_manager = InMemoryStateManager()


# Maintain backward compatibility with the functional API
async def add_active_run(run_id: str):
    await _manager.add_active_run(run_id)


async def remove_run(run_id: str):
    await _manager.remove_run(run_id)


async def abort_run(run_id: str):
    await _manager.abort_run(run_id)


async def is_aborted(run_id: str) -> bool:
    return await _manager.is_aborted(run_id)


def check_abort(run_id: str):
    if _manager.is_aborted_sync(run_id):
        raise RuntimeError(f"Run {run_id} was aborted by user.")


async def get_active_runs() -> list[str]:
    return await _manager.get_active_runs()


# Export the globals as empty sets for any remaining direct access (though not recommended)
# Since they were used as sets in the original code, we keep them for compatibility
# but they will be out of sync with the manager.
# A better approach is to replace all direct accesses.
ACTIVE_RUNS: set[str] = set()
ABORTED_RUNS: set[str] = set()
RUNS_LOCK = asyncio.Lock()

from contextvars import ContextVar

_current_run_id: ContextVar[str | None] = ContextVar("current_run_id", default=None)

def set_current_run_id(run_id: str | None):
    _current_run_id.set(run_id)

def get_current_run_id() -> str | None:
    return _current_run_id.get()
