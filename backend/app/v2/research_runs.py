from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import Engine, func, or_, select
from sqlalchemy.orm import Session

from app.v2.contracts import (
    CheckpointProjection,
    CreateResearchRun,
    RunEventProjection,
    RunProjection,
    RunStepProjection,
    RunTargetProjection,
    StepAttemptProjection,
    StepLease,
)
from app.v2.domain import RunOutcome, RunStatus, StepKind, legal_transition
from app.v2.models import (
    Checkpoint,
    OutboxEvent,
    Run,
    RunStep,
    RunTarget,
    StepAttempt,
)


class IdempotencyConflictError(ValueError):
    def __init__(self) -> None:
        super().__init__("idempotency key was already used with a different payload")


class IllegalTransitionError(ValueError):
    def __init__(self) -> None:
        super().__init__("operation is illegal in the current run state")


class LeaseConflictError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("step lease is no longer active")


class RetryLimitError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("step retry limit reached")


class MissingRetryDueError(ValueError):
    def __init__(self) -> None:
        super().__init__("retry_at is required for retryable failures")


class RunNotFoundError(LookupError):
    pass


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _transition(record: Run | RunStep, target: RunStatus) -> None:
    current = RunStatus(record.status)
    if current == target:
        return
    if not legal_transition(current, target):
        raise IllegalTransitionError
    record.status = target.value


class ResearchRunKernel:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def create(self, command: CreateResearchRun, idempotency_key: str) -> RunProjection:
        encoded = json.dumps(
            command.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
        payload_hash = hashlib.sha256(encoded).hexdigest()
        with Session(self.engine) as session, session.begin():
            existing = session.scalar(
                select(Run).where(Run.idempotency_key == idempotency_key)
            )
            if existing is not None:
                if existing.payload_hash != payload_hash:
                    raise IdempotencyConflictError
                run_id = existing.id
            else:
                run_id = _id("run")
                session.add(
                    Run(
                        id=run_id,
                        kind="RESEARCH",
                        status=RunStatus.PENDING.value,
                        idempotency_key=idempotency_key,
                        payload_hash=payload_hash,
                        objective=command.objective,
                        scope_json=dict(command.scope),
                        max_attempts=command.max_attempts,
                    )
                )
                session.flush()
                for target in command.targets:
                    target_id = _id("target")
                    session.add(
                        RunTarget(
                            id=target_id,
                            run_id=run_id,
                            world_id=target.world_id,
                            objective=target.objective,
                            scope_json=dict(target.scope),
                        )
                    )
                    session.flush()
                    for position, kind in enumerate(StepKind):
                        session.add(
                            RunStep(
                                id=_id("step"),
                                run_id=run_id,
                                target_id=target_id,
                                status=RunStatus.PENDING.value,
                                idempotency_key=f"{run_id}:{target_id}:{position}",
                                kind=kind.value,
                                position=position,
                            )
                        )
                session.add(
                    OutboxEvent(
                        id=_id("event"),
                        run_id=run_id,
                        event_type="RUN_CREATED",
                        payload_json={"payload_hash": payload_hash},
                        effect_key=f"run-created:{run_id}",
                    )
                )
        return self.get(run_id)

    def get(self, run_id: str) -> RunProjection:
        with Session(self.engine) as session:
            run = session.get(Run, run_id)
            if run is None:
                raise RunNotFoundError(run_id)
            targets = session.scalars(
                select(RunTarget)
                .where(RunTarget.run_id == run_id)
                .order_by(RunTarget.world_id)
            ).all()
            steps = session.scalars(
                select(RunStep)
                .where(RunStep.run_id == run_id)
                .order_by(RunStep.position)
            ).all()
            attempts = session.scalars(
                select(StepAttempt)
                .join(RunStep)
                .where(RunStep.run_id == run_id)
                .order_by(StepAttempt.step_id, StepAttempt.attempt_number)
            ).all()
            attempts_by_step: dict[str, list[StepAttempt]] = {}
            for attempt in attempts:
                attempts_by_step.setdefault(attempt.step_id, []).append(attempt)
            return RunProjection(
                id=run.id,
                status=RunStatus(run.status),
                outcome=RunOutcome(run.outcome) if run.outcome else None,
                objective=run.objective,
                scope=dict(run.scope_json),
                cancel_requested_at=_aware(run.cancel_requested_at),
                targets=tuple(
                    RunTargetProjection(
                        id=target.id,
                        world_id=target.world_id,
                        objective=target.objective,
                        scope=dict(target.scope_json),
                        outcome=RunOutcome(target.outcome) if target.outcome else None,
                        error=target.error,
                    )
                    for target in targets
                ),
                steps=tuple(
                    RunStepProjection(
                        id=step.id,
                        target_id=step.target_id,
                        world_id=next(
                            target.world_id
                            for target in targets
                            if target.id == step.target_id
                        ),
                        kind=StepKind(step.kind),
                        position=step.position,
                        status=RunStatus(step.status),
                        attempt_count=step.attempt_count,
                        retry_due_at=_aware(step.retry_due_at),
                        output_refs=tuple(step.output_refs_json),
                        error=step.error,
                        attempts=tuple(
                            StepAttemptProjection(
                                attempt_number=attempt.attempt_number,
                                status=RunStatus(attempt.status),
                                owner=attempt.owner,
                                lease_expires_at=_aware(attempt.lease_expires_at),
                                started_at=_aware(attempt.started_at),
                                finished_at=_aware(attempt.finished_at),
                                error=attempt.error,
                            )
                            for attempt in attempts_by_step.get(step.id, ())
                        ),
                    )
                    for step in steps
                ),
            )

    def append_step(
        self, run_id: str, target_id: str, kind: StepKind, effect_key: str
    ) -> RunStepProjection:
        with Session(self.engine) as session, session.begin():
            existing = session.scalar(
                select(RunStep).where(RunStep.idempotency_key == effect_key)
            )
            if existing is not None:
                if (
                    existing.run_id != run_id
                    or existing.target_id != target_id
                    or existing.kind != kind.value
                ):
                    raise IdempotencyConflictError
                step_id = existing.id
            else:
                run = self._run(session, run_id)
                if RunStatus(run.status) in {
                    RunStatus.CANCELLED,
                    RunStatus.SUCCEEDED,
                    RunStatus.FAILED,
                }:
                    raise IllegalTransitionError
                position = session.scalar(
                    select(func.max(RunStep.position)).where(
                        RunStep.target_id == target_id
                    )
                )
                step_id = _id("step")
                session.add(
                    RunStep(
                        id=step_id,
                        run_id=run_id,
                        target_id=target_id,
                        status=RunStatus.PENDING.value,
                        idempotency_key=effect_key,
                        kind=kind.value,
                        position=(position if position is not None else -1) + 1,
                    )
                )
        projection = self.get(run_id)
        return next(step for step in projection.steps if step.id == step_id)

    def events(self, run_id: str) -> tuple[RunEventProjection, ...]:
        with Session(self.engine) as session:
            if session.get(Run, run_id) is None:
                raise RunNotFoundError(run_id)
            rows = session.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.run_id == run_id)
                .order_by(OutboxEvent.created_at, OutboxEvent.id)
            ).all()
            return tuple(
                RunEventProjection(
                    id=row.id,
                    event_type=row.event_type,
                    payload=dict(row.payload_json),
                    created_at=_aware(row.created_at),
                )
                for row in rows
            )

    def lease_next(
        self,
        owner: str,
        now: datetime,
        duration: timedelta,
        *,
        run_id: str | None = None,
    ) -> StepLease | None:
        with Session(self.engine) as session:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            query = (
                select(RunStep)
                .join(Run)
                .where(
                    Run.status.in_(
                        [
                            RunStatus.PENDING.value,
                            RunStatus.RUNNING.value,
                            RunStatus.WAITING_RETRY.value,
                        ]
                    ),
                    or_(
                        RunStep.status == RunStatus.PENDING.value,
                        (RunStep.status == RunStatus.WAITING_RETRY.value)
                        & (RunStep.retry_due_at <= now),
                    ),
                )
            )
            if run_id is not None:
                query = query.where(RunStep.run_id == run_id)
            candidates = session.scalars(
                query.order_by(Run.created_at, RunStep.position, RunStep.target_id)
            ).all()
            step = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.position == 0
                    or session.scalar(
                        select(func.count())
                        .select_from(RunStep)
                        .where(
                            RunStep.target_id == candidate.target_id,
                            RunStep.position < candidate.position,
                            RunStep.status != RunStatus.SUCCEEDED.value,
                        )
                    )
                    == 0
                ),
                None,
            )
            if step is None:
                active = (
                    session.scalar(
                        select(RunStep.id).where(
                            RunStep.run_id == run_id,
                            RunStep.status == RunStatus.RUNNING.value,
                        )
                    )
                    if run_id
                    else None
                )
                session.commit()
                if active is not None:
                    raise LeaseConflictError
                return None
            run = session.get(Run, step.run_id)
            assert run is not None
            _transition(step, RunStatus.RUNNING)
            if RunStatus(run.status) in {RunStatus.PENDING, RunStatus.WAITING_RETRY}:
                _transition(run, RunStatus.RUNNING)
            step.attempt_count += 1
            step.lease_owner = owner
            step.lease_expires_at = now + duration
            step.retry_due_at = None
            attempt = StepAttempt(
                id=_id("attempt"),
                step_id=step.id,
                attempt_number=step.attempt_count,
                status=RunStatus.RUNNING.value,
                owner=owner,
                lease_expires_at=step.lease_expires_at,
                started_at=now,
            )
            session.add(attempt)
            result = StepLease(
                step_id=step.id,
                run_id=step.run_id,
                target_id=step.target_id,
                world_id=session.get(RunTarget, step.target_id).world_id,
                kind=StepKind(step.kind),
                owner=owner,
                attempt_number=step.attempt_count,
                lease_expires_at=step.lease_expires_at,
            )
            session.commit()
            return result

    def reconcile_startup(self, now: datetime) -> int:
        reclaimed = 0
        with Session(self.engine) as session, session.begin():
            steps = session.scalars(
                select(RunStep).where(
                    RunStep.status == RunStatus.RUNNING.value,
                    RunStep.lease_expires_at < now,
                )
            ).all()
            for step in steps:
                attempt = session.scalar(
                    select(StepAttempt).where(
                        StepAttempt.step_id == step.id,
                        StepAttempt.attempt_number == step.attempt_count,
                    )
                )
                run = session.get(Run, step.run_id)
                assert run is not None
                if RunStatus(run.status) is RunStatus.CANCELLING:
                    assert attempt is not None
                    self._cancel_run_at_boundary(session, run, step, attempt, now)
                    reclaimed += 1
                    continue
                if attempt is not None:
                    attempt.status = RunStatus.FAILED.value
                    attempt.error = "lease_expired"
                    attempt.finished_at = now
                step.status = RunStatus.PENDING.value
                step.lease_owner = None
                step.lease_expires_at = None
                reclaimed += 1
        return reclaimed

    def checkpoint_success(
        self,
        lease: StepLease,
        *,
        effect_key: str,
        output_refs: tuple[str, ...],
        state: dict[str, object],
        now: datetime,
    ) -> CheckpointProjection | None:
        with Session(self.engine) as session, session.begin():
            existing = session.scalar(
                select(Checkpoint).where(Checkpoint.effect_key == effect_key)
            )
            if existing is not None:
                return CheckpointProjection(
                    id=existing.id,
                    step_id=existing.step_id,
                    effect_key=existing.effect_key,
                )
            step, attempt = self._validate_lease(session, lease, now)
            run = session.get(Run, step.run_id)
            assert run is not None
            if RunStatus(run.status) is RunStatus.CANCELLING:
                self._cancel_run_at_boundary(session, run, step, attempt, now)
                return None
            checkpoint = Checkpoint(
                id=_id("checkpoint"),
                step_id=step.id,
                state_json=state,
                effect_key=effect_key,
                output_refs_json=list(output_refs),
                created_at=now,
            )
            session.add(checkpoint)
            _transition(step, RunStatus.SUCCEEDED)
            step.output_refs_json = list(output_refs)
            step.lease_owner = None
            step.lease_expires_at = None
            attempt.status = RunStatus.SUCCEEDED.value
            attempt.finished_at = now
            if step.kind == StepKind.COMPLETE.value and not state.get("continue_loop"):
                target = session.get(RunTarget, step.target_id)
                assert target is not None
                target.outcome = str(state.get("outcome", RunOutcome.COMPLETE.value))
                target.error = None
                self._aggregate_targets(session, run, now)
            session.add(
                OutboxEvent(
                    id=_id("event"),
                    run_id=step.run_id,
                    event_type="STEP_SUCCEEDED",
                    payload_json={"step_id": step.id, "output_refs": list(output_refs)},
                    effect_key=f"checkpoint:{effect_key}",
                    created_at=now,
                )
            )
            return CheckpointProjection(
                id=checkpoint.id, step_id=step.id, effect_key=effect_key
            )

    def checkpoint_failure(
        self,
        lease: StepLease,
        error: str,
        *,
        retryable: bool,
        retry_at: datetime | None,
        now: datetime,
    ) -> None:
        exhausted = False
        with Session(self.engine) as session, session.begin():
            step, attempt = self._validate_lease(session, lease, now)
            run = session.get(Run, step.run_id)
            assert run is not None
            if RunStatus(run.status) is RunStatus.CANCELLING:
                self._cancel_run_at_boundary(session, run, step, attempt, now)
                return
            attempt.status = RunStatus.FAILED.value
            attempt.finished_at = now
            attempt.error = error
            step.error = error
            step.lease_owner = None
            step.lease_expires_at = None
            if retryable and step.attempt_count < run.max_attempts:
                if retry_at is None:
                    raise MissingRetryDueError
                _transition(step, RunStatus.WAITING_RETRY)
                step.retry_due_at = retry_at
                _transition(run, RunStatus.WAITING_RETRY)
            else:
                _transition(step, RunStatus.FAILED)
                target = session.get(RunTarget, step.target_id)
                assert target is not None
                target.outcome = RunOutcome.FAILED.value
                target.error = error
                session.query(RunStep).filter(
                    RunStep.target_id == step.target_id,
                    RunStep.status == RunStatus.PENDING.value,
                ).update({RunStep.status: RunStatus.CANCELLED.value})
                self._aggregate_targets(session, run, now)
                exhausted = retryable
            session.add(
                OutboxEvent(
                    id=_id("event"),
                    run_id=run.id,
                    event_type="STEP_FAILED",
                    payload_json={"step_id": step.id, "error": error},
                    effect_key=f"failure:{step.id}:{step.attempt_count}",
                    created_at=now,
                )
            )
        if exhausted:
            raise RetryLimitError

    def request_cancel(self, run_id: str, now: datetime) -> RunProjection:
        with Session(self.engine) as session, session.begin():
            run = self._run(session, run_id)
            if RunStatus(run.status) in {
                RunStatus.CANCELLED,
                RunStatus.SUCCEEDED,
                RunStatus.FAILED,
            }:
                raise IllegalTransitionError
            run.cancel_requested_at = now
            active = session.scalar(
                select(RunStep.id).where(
                    RunStep.run_id == run_id,
                    RunStep.status == RunStatus.RUNNING.value,
                )
            )
            if active is None:
                run.status = RunStatus.CANCELLED.value
                run.outcome = RunOutcome.CANCELLED.value
                session.query(RunStep).filter(
                    RunStep.run_id == run_id,
                    RunStep.status.not_in(
                        [RunStatus.SUCCEEDED.value, RunStatus.FAILED.value]
                    ),
                ).update({RunStep.status: RunStatus.CANCELLED.value})
            else:
                _transition(run, RunStatus.CANCELLING)
            self._event(
                session, run_id, "CANCEL_REQUESTED", {}, f"cancel:{run_id}", now
            )
        return self.get(run_id)

    def cancel_at_safe_boundary(self, lease: StepLease, now: datetime) -> RunProjection:
        with Session(self.engine) as session, session.begin():
            step, attempt = self._validate_lease(session, lease, now)
            run = self._run(session, lease.run_id)
            if RunStatus(run.status) is not RunStatus.CANCELLING:
                raise IllegalTransitionError
            self._cancel_run_at_boundary(session, run, step, attempt, now)
        return self.get(lease.run_id)

    def record_target_outcome(
        self,
        run_id: str,
        world_id: str,
        outcome: RunOutcome,
        error: str | None,
        now: datetime,
    ) -> None:
        with Session(self.engine) as session, session.begin():
            target = session.scalar(
                select(RunTarget).where(
                    RunTarget.run_id == run_id, RunTarget.world_id == world_id
                )
            )
            if target is None:
                raise LookupError(world_id)
            target.outcome = outcome.value
            target.error = error
            self._event(
                session,
                run_id,
                "TARGET_FINISHED",
                {"world_id": world_id, "outcome": outcome.value, "error": error},
                f"target:{run_id}:{world_id}",
                now,
            )

    def finish_from_targets(self, run_id: str, now: datetime) -> RunProjection:
        with Session(self.engine) as session, session.begin():
            run = self._run(session, run_id)
            targets = session.scalars(
                select(RunTarget).where(RunTarget.run_id == run_id)
            ).all()
            if not targets or any(target.outcome is None for target in targets):
                raise IllegalTransitionError
            complete_steps = session.scalars(
                select(RunStep).where(
                    RunStep.run_id == run_id, RunStep.kind == StepKind.COMPLETE.value
                )
            ).all()
            if any(step.status != RunStatus.SUCCEEDED.value for step in complete_steps):
                raise IllegalTransitionError
            self._aggregate_targets(session, run, now)
        return self.get(run_id)

    def resume(self, run_id: str) -> RunProjection:
        with Session(self.engine) as session, session.begin():
            run = self._run(session, run_id)
            if RunStatus(run.status) is not RunStatus.WAITING_INPUT:
                raise IllegalTransitionError
            _transition(run, RunStatus.RUNNING)
        return self.get(run_id)

    def retry(self, run_id: str, now: datetime) -> RunProjection:
        with Session(self.engine) as session, session.begin():
            run = self._run(session, run_id)
            retryable_status = RunStatus(run.status) is RunStatus.FAILED or (
                RunStatus(run.status) is RunStatus.SUCCEEDED
                and run.outcome == RunOutcome.PARTIAL.value
            )
            if not retryable_status:
                raise IllegalTransitionError
            steps = session.scalars(
                select(RunStep).where(
                    RunStep.run_id == run_id,
                    RunStep.status == RunStatus.FAILED.value,
                    RunStep.attempt_count < run.max_attempts,
                )
            ).all()
            partial_targets = (
                session.scalars(
                    select(RunTarget).where(
                        RunTarget.run_id == run_id,
                        RunTarget.outcome == RunOutcome.PARTIAL.value,
                    )
                ).all()
                if run.outcome == RunOutcome.PARTIAL.value
                else []
            )
            if not steps and not partial_targets:
                raise IllegalTransitionError
            run.status = RunStatus.WAITING_RETRY.value
            run.outcome = None
            retried_target_ids: set[str] = set()
            for step in steps:
                step.status = RunStatus.WAITING_RETRY.value
                step.retry_due_at = now
                target = session.get(RunTarget, step.target_id)
                assert target is not None
                target.outcome = None
                target.error = None
                retried_target_ids.add(target.id)
                session.query(RunStep).filter(
                    RunStep.target_id == step.target_id,
                    RunStep.position > step.position,
                    RunStep.status == RunStatus.CANCELLED.value,
                ).update(
                    {
                        RunStep.status: RunStatus.PENDING.value,
                        RunStep.error: None,
                        RunStep.retry_due_at: None,
                    }
                )
            for target in partial_targets:
                target.outcome = None
                target.error = None
                retried_target_ids.add(target.id)
                position = session.scalar(
                    select(func.max(RunStep.position)).where(
                        RunStep.target_id == target.id
                    )
                )
                next_position = (position if position is not None else -1) + 1
                for offset, kind in enumerate(list(StepKind)[1:]):
                    session.add(
                        RunStep(
                            id=_id("step"),
                            run_id=run.id,
                            target_id=target.id,
                            status=RunStatus.PENDING.value,
                            idempotency_key=(
                                f"manual-retry:{run.id}:{target.id}:"
                                f"{next_position}:{kind.value}"
                            ),
                            kind=kind.value,
                            position=next_position + offset,
                        )
                    )
            retry_number = (
                session.scalar(
                    select(func.count())
                    .select_from(OutboxEvent)
                    .where(
                        OutboxEvent.run_id == run.id,
                        OutboxEvent.event_type == "RUN_RETRIED",
                    )
                )
                or 0
            ) + 1
            self._event(
                session,
                run.id,
                "RUN_RETRIED",
                {"target_count": len(retried_target_ids)},
                f"retry:{run.id}:{retry_number}",
                now,
            )
        return self.get(run_id)

    @staticmethod
    def _cancel_run_at_boundary(
        session: Session,
        run: Run,
        step: RunStep,
        attempt: StepAttempt,
        now: datetime,
    ) -> None:
        step.status = RunStatus.CANCELLED.value
        step.lease_owner = None
        step.lease_expires_at = None
        attempt.status = RunStatus.CANCELLED.value
        attempt.finished_at = now
        session.query(RunStep).filter(
            RunStep.run_id == run.id,
            RunStep.status.in_(
                [
                    RunStatus.PENDING.value,
                    RunStatus.WAITING_RETRY.value,
                    RunStatus.WAITING_INPUT.value,
                ]
            ),
        ).update({RunStep.status: RunStatus.CANCELLED.value})
        active = session.scalar(
            select(func.count())
            .select_from(RunStep)
            .where(
                RunStep.run_id == run.id,
                RunStep.status == RunStatus.RUNNING.value,
            )
        )
        if not active:
            run.status = RunStatus.CANCELLED.value
            run.outcome = RunOutcome.CANCELLED.value
            ResearchRunKernel._event(
                session, run.id, "RUN_CANCELLED", {}, f"cancelled:{run.id}", now
            )

    @staticmethod
    def _aggregate_targets(session: Session, run: Run, now: datetime) -> None:
        targets = session.scalars(
            select(RunTarget).where(RunTarget.run_id == run.id)
        ).all()
        if not targets or any(target.outcome is None for target in targets):
            return
        outcomes = {RunOutcome(target.outcome) for target in targets}
        if outcomes == {RunOutcome.COMPLETE}:
            outcome, status = RunOutcome.COMPLETE, RunStatus.SUCCEEDED
        elif outcomes == {RunOutcome.FAILED}:
            outcome, status = RunOutcome.FAILED, RunStatus.FAILED
        else:
            outcome, status = RunOutcome.PARTIAL, RunStatus.SUCCEEDED
        run.status = status.value
        run.outcome = outcome.value
        existing = session.scalar(
            select(OutboxEvent).where(OutboxEvent.effect_key == f"finished:{run.id}")
        )
        if existing is None:
            ResearchRunKernel._event(
                session,
                run.id,
                "RUN_FINISHED",
                {"outcome": outcome.value},
                f"finished:{run.id}",
                now,
            )

    @staticmethod
    def _validate_lease(
        session: Session, lease: StepLease, now: datetime
    ) -> tuple[RunStep, StepAttempt]:
        step = session.get(RunStep, lease.step_id)
        if (
            step is None
            or step.run_id != lease.run_id
            or step.status != RunStatus.RUNNING.value
            or step.lease_owner != lease.owner
            or step.attempt_count != lease.attempt_number
            or step.lease_expires_at is None
            or _aware(step.lease_expires_at) < _aware(now)
        ):
            raise LeaseConflictError
        attempt = session.scalar(
            select(StepAttempt).where(
                StepAttempt.step_id == step.id,
                StepAttempt.attempt_number == lease.attempt_number,
            )
        )
        if attempt is None:
            raise LeaseConflictError
        return step, attempt

    @staticmethod
    def _run(session: Session, run_id: str) -> Run:
        run = session.get(Run, run_id)
        if run is None:
            raise RunNotFoundError(run_id)
        return run

    @staticmethod
    def _event(
        session: Session,
        run_id: str,
        event_type: str,
        payload: dict[str, object],
        effect_key: str,
        now: datetime,
    ) -> None:
        session.add(
            OutboxEvent(
                id=_id("event"),
                run_id=run_id,
                event_type=event_type,
                payload_json=payload,
                effect_key=effect_key,
                created_at=now,
            )
        )
