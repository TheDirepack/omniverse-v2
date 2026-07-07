from contextvars import ContextVar

_current_universe: ContextVar[str] = ContextVar("current_universe", default="")


def get_current_universe() -> str:
    return _current_universe.get()


def set_current_universe(name: str) -> None:
    _current_universe.set(name)
