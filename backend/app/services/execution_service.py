from sqlmodel import Session

from app.core.agent_logger import agent_logger
from app.db.schema import ExecutionState
from app.db.session import engine
from app.repositories.execution import ExecutionRepository


class ExecutionService:
    def __init__(self, session: Session | None = None):
        self.session = session
        self._repo = None

    @property
    def repo(self) -> ExecutionRepository:
        if self._repo is None:
            self._repo = ExecutionRepository(self.session or Session(engine))
        return self._repo

    def log_transition(
        self,
        run_id: str,
        node_name: str,
        thought: str,
        status: str,
        state: dict,
        duration_ms: float | None = None,
        token_usage: int | None = None,
        cost: float | None = None,
    ):
        import json

        snapshot_dict = {k: v for k, v in state.items() if k != "run_id"}
        snapshot_str = json.dumps(snapshot_dict, default=str)
        log_entry = ExecutionState(
            run_id=run_id,
            node_name=node_name,
            thought=thought,
            status=status,
            state_snapshot=snapshot_str,
            duration_ms=duration_ms,
            token_usage=token_usage,
            cost=cost,
        )
        self.repo.create_log(log_entry)
        self.repo.session.commit()

        # Mirror to file logs for parity with live logs
        agent_logger.log(
            agent=node_name,
            event_type=status,
            content=thought,
            model="system",
            key_id="system",
        )

    def clear_logs(self):
        self.repo.clear_logs()
        self.repo.session.commit()

    def close(self):
        """Closes the internal session if it was lazily created."""
        if self._repo and not self.session:
            self._repo.session.close()
            self._repo = None
