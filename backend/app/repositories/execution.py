from typing import Sequence
from sqlmodel import Session, select, delete
from app.db.schema import ExecutionState

class ExecutionRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_log(self, execution_state: ExecutionState) -> ExecutionState:
        self.session.add(execution_state)
        self.session.commit()
        self.session.refresh(execution_state)
        return execution_state

    def get_recent_logs(self, limit: int = 50) -> Sequence[ExecutionState]:
        return self.session.exec(select(ExecutionState).order_by(ExecutionState.created_at.desc()).limit(limit)).all()

    def get_logs_for_run(self, run_id: str, last_id: int) -> Sequence[ExecutionState]:
        return self.session.exec(
            select(ExecutionState).where(
                ExecutionState.run_id == run_id,
                ExecutionState.id > last_id
            ).order_by(ExecutionState.id)
        ).all()

    def clear_logs(self):
        self.session.exec(delete(ExecutionState))
        self.session.commit()
