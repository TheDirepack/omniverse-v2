from collections.abc import Sequence

from sqlmodel import Session, delete, select

from app.db.schema import Claim, ClaimAttribute, ExecutionState, UnconfirmedClaim


class ExecutionRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_all_runs(self, limit: int = 100) -> Sequence[ExecutionState]:
        # Get the latest state for each unique run_id
        return self.session.exec(
            select(ExecutionState)
            .order_by(ExecutionState.created_at.desc())
            .distinct(ExecutionState.run_id)
            .limit(limit)
        ).all()

    def create_log(self, execution_state: ExecutionState) -> ExecutionState:
        self.session.add(execution_state)
        return execution_state

    def get_recent_logs(self, limit: int = 50) -> Sequence[ExecutionState]:
        return self.session.exec(
            select(ExecutionState)
            .order_by(ExecutionState.created_at.desc())
            .limit(limit)
        ).all()

    def get_logs_for_run(self, run_id: str, last_id: int) -> Sequence[ExecutionState]:
        return self.session.exec(
            select(ExecutionState)
            .where(ExecutionState.run_id == run_id, ExecutionState.id > last_id)
            .order_by(ExecutionState.id)
        ).all()

    def clear_logs(self):
        self.session.exec(delete(ExecutionState))

    def delete_all_claims(self):
        # Delete ClaimAttributes first (foreign key constraint)
        self.session.exec(delete(ClaimAttribute))
        # Delete claims
        self.session.exec(delete(Claim))
        # Delete unconfirmed claims
        self.session.exec(delete(UnconfirmedClaim))
        return {"status": "success"}
