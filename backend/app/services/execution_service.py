from typing import List, Optional, Sequence, Dict, Any
from sqlmodel import Session
from app.db.session import engine
from app.db.schema import ExecutionState
from app.repositories.execution import ExecutionRepository
from app.core.agent_logger import agent_logger

class ExecutionService:
    def __init__(self, session: Optional[Session] = None):
        self.session = session or Session(engine)
        self.repo = ExecutionRepository(self.session)

    def log_transition(self, run_id: str, node_name: str, thought: str, status: str, state: dict):
        import json
        snapshot_str = json.dumps({k: v for k, v in state.items() if k != "run_id"}, default=str)
        log_entry = ExecutionState(
            run_id=run_id,
            node_name=node_name,
            thought=thought,
            status=status,
            state_snapshot=snapshot_str
        )
        self.repo.create_log(log_entry)
        
        # Mirror to file logs for parity with live logs
        agent_logger.log(
            agent=node_name,
            event_type=status,
            content=thought,
            model="system",
            key_id="system"
        )

    def get_recent_logs(self, limit: int = 50) -> Sequence[ExecutionState]:
        return self.repo.get_recent_logs(limit)

    def get_logs_for_run(self, run_id: str, last_id: int) -> Sequence[ExecutionState]:
        return self.repo.get_logs_for_run(run_id, last_id)

    def clear_logs(self):
        self.repo.clear_logs()

