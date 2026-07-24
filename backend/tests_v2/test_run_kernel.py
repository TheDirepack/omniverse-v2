from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.v2.contracts import CreateResearchRun, ResearchRunTargetInput
from app.v2.db import bootstrap_schema, create_sqlite_engine
from app.v2.domain import RunOutcome, RunStatus, StepKind, legal_transition
from app.v2.models import (
    Checkpoint,
    OutboxEvent,
    Run,
    RunStep,
    RunTarget,
    StepAttempt,
    World,
)
from app.v2.research_runs import (
    IdempotencyConflictError,
    IllegalTransitionError,
    LeaseConflictError,
    ResearchRunKernel,
    RetryLimitError,
)

UTC = timezone.utc
NOW = datetime(2026, 7, 23, 12, tzinfo=UTC)


@pytest.fixture
def engine(isolated_paths: dict[str, Path]) -> Engine:
    value = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(value)
    with Session(value) as session, session.begin():
        session.add_all(
            [
                World(id="w1", name="One", franchise="F", category="SF"),
                World(id="w2", name="Two", franchise="F", category="SF"),
            ]
        )
    return value


def command(*world_ids: str) -> CreateResearchRun:
    return CreateResearchRun(
        objective="Map documented capabilities",
        scope={"continuity": "primary", "depth": "standard"},
        targets=tuple(
            ResearchRunTargetInput(world_id=world_id, objective=f"Research {world_id}")
            for world_id in world_ids
        ),
        max_attempts=2,
    )


@pytest.mark.unit
def test_statuses_have_an_explicit_legal_transition_table() -> None:
    assert legal_transition(RunStatus.PENDING, RunStatus.RUNNING)
    assert legal_transition(RunStatus.RUNNING, RunStatus.WAITING_RETRY)
    assert legal_transition(RunStatus.RUNNING, RunStatus.CANCELLING)
    assert legal_transition(RunStatus.CANCELLING, RunStatus.CANCELLED)
    assert not legal_transition(RunStatus.SUCCEEDED, RunStatus.RUNNING)
    assert not legal_transition(RunStatus.FAILED, RunStatus.SUCCEEDED)
    assert RunOutcome.PARTIAL.value == "PARTIAL"


@pytest.mark.integration
def test_create_is_payload_idempotent_and_steps_are_deterministic(
    engine: Engine,
) -> None:
    kernel = ResearchRunKernel(engine)
    created = kernel.create(command("w1", "w2"), "create-key")
    repeated = kernel.create(command("w1", "w2"), "create-key")
    assert repeated.id == created.id
    projection = kernel.get(created.id)
    assert len(projection.steps) == len(StepKind) * 2
    for target in projection.targets:
        target_steps = [
            step for step in projection.steps if step.target_id == target.id
        ]
        assert [step.kind for step in target_steps] == list(StepKind)
        assert [step.position for step in target_steps] == list(range(10))
        assert {step.world_id for step in target_steps} == {target.world_id}

    changed = command("w1")
    with pytest.raises(IdempotencyConflictError):
        kernel.create(changed, "create-key")


@pytest.mark.integration
def test_lease_attempt_and_expired_reconciliation_are_durable(engine: Engine) -> None:
    run = ResearchRunKernel(engine).create(command("w1"), "lease-run")
    kernel = ResearchRunKernel(engine)
    lease = kernel.lease_next("worker-a", NOW, timedelta(minutes=5))
    assert lease is not None
    assert lease.run_id == run.id
    assert lease.target_id == run.targets[0].id
    assert lease.world_id == "w1"
    assert lease.kind is StepKind.INVENTORY
    assert lease.attempt_number == 1
    with pytest.raises(LeaseConflictError):
        kernel.lease_next("worker-b", NOW, timedelta(minutes=5), run_id=run.id)

    restarted = ResearchRunKernel(engine)
    assert restarted.reconcile_startup(NOW + timedelta(minutes=6)) == 1
    reclaimed = restarted.lease_next(
        "worker-b", NOW + timedelta(minutes=6), timedelta(minutes=5), run_id=run.id
    )
    assert reclaimed is not None
    assert reclaimed.step_id == lease.step_id
    assert reclaimed.attempt_number == 2


@pytest.mark.integration
def test_checkpoint_is_atomic_and_duplicate_effect_is_a_noop(engine: Engine) -> None:
    kernel = ResearchRunKernel(engine)
    run = kernel.create(command("w1"), "checkpoint-run")
    lease = kernel.lease_next("worker", NOW, timedelta(minutes=5), run_id=run.id)
    assert lease is not None
    first = kernel.checkpoint_success(
        lease,
        effect_key="inventory:w1:v1",
        output_refs=("blob:sha256:abc",),
        state={"cursor": 3},
        now=NOW,
    )
    repeated = ResearchRunKernel(engine).checkpoint_success(
        lease,
        effect_key="inventory:w1:v1",
        output_refs=("blob:sha256:abc",),
        state={"cursor": 3},
        now=NOW,
    )
    assert repeated.id == first.id
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Checkpoint)) == 1
        assert session.scalar(select(func.count()).select_from(OutboxEvent)) == 2
        assert (
            session.scalar(
                select(func.count())
                .select_from(RunStep)
                .where(RunStep.status == RunStatus.RUNNING.value)
            )
            == 0
        )


@pytest.mark.integration
def test_workflow_can_append_a_deduplicated_loop_step(engine: Engine) -> None:
    kernel = ResearchRunKernel(engine)
    run = kernel.create(command("w1"), "loop-run")
    target_id = run.targets[0].id
    appended = kernel.append_step(run.id, target_id, StepKind.SCOUT, "gap-scout:w1:1")
    repeated = kernel.append_step(run.id, target_id, StepKind.SCOUT, "gap-scout:w1:1")
    assert appended.id == repeated.id
    assert appended.position == 10
    assert kernel.get(run.id).steps[-1].kind is StepKind.SCOUT


@pytest.mark.integration
def test_targets_have_independent_ordered_step_chains(engine: Engine) -> None:
    kernel = ResearchRunKernel(engine)
    run = kernel.create(command("w1", "w2"), "target-chains")
    first = kernel.lease_next("worker", NOW, timedelta(minutes=5), run_id=run.id)
    assert first is not None
    kernel.checkpoint_success(
        first,
        effect_key=f"ok:{first.step_id}",
        output_refs=(),
        state={},
        now=NOW,
    )
    second = kernel.lease_next("worker", NOW, timedelta(minutes=5), run_id=run.id)
    assert second is not None
    assert second.target_id != first.target_id
    assert second.kind is StepKind.INVENTORY


@pytest.mark.integration
def test_run_aggregates_only_after_every_target_complete_step(engine: Engine) -> None:
    kernel = ResearchRunKernel(engine)
    run = kernel.create(command("w1", "w2"), "target-aggregate")
    kernel.record_target_outcome(run.id, "w1", RunOutcome.COMPLETE, None, NOW)
    with pytest.raises(IllegalTransitionError):
        kernel.finish_from_targets(run.id, NOW)


@pytest.mark.integration
def test_multi_target_failure_finishes_partial_not_false_success(
    engine: Engine,
) -> None:
    kernel = ResearchRunKernel(engine)
    run = kernel.create(command("w1", "w2"), "partial-run")
    kernel.record_target_outcome(run.id, "w1", RunOutcome.COMPLETE, None, NOW)
    kernel.record_target_outcome(run.id, "w2", RunOutcome.FAILED, "blocked", NOW)
    with pytest.raises(IllegalTransitionError):
        kernel.finish_from_targets(run.id, NOW)
    projection = kernel.get(run.id)
    assert projection.outcome is None
    assert {target.world_id: target.outcome for target in projection.targets} == {
        "w1": RunOutcome.COMPLETE,
        "w2": RunOutcome.FAILED,
    }
    assert projection.targets[1].error == "blocked"


@pytest.mark.integration
def test_cancel_request_survives_restart_and_applies_at_safe_boundary(
    engine: Engine,
) -> None:
    kernel = ResearchRunKernel(engine)
    run = kernel.create(command("w1"), "cancel-run")
    lease = kernel.lease_next("worker", NOW, timedelta(minutes=5), run_id=run.id)
    assert lease is not None
    requested = kernel.request_cancel(run.id, NOW)
    assert requested.status is RunStatus.CANCELLING
    assert ResearchRunKernel(engine).get(run.id).cancel_requested_at == NOW

    cancelled = ResearchRunKernel(engine).cancel_at_safe_boundary(lease, NOW)
    assert cancelled.status is RunStatus.CANCELLED
    assert cancelled.outcome is RunOutcome.CANCELLED


@pytest.mark.integration
def test_in_flight_success_observes_cancel_request_atomically(engine: Engine) -> None:
    kernel = ResearchRunKernel(engine)
    run = kernel.create(command("w1"), "cancel-during-step")
    lease = kernel.lease_next("worker", NOW, timedelta(minutes=5), run_id=run.id)
    assert lease is not None

    kernel.request_cancel(run.id, NOW)
    checkpoint = kernel.checkpoint_success(
        lease,
        effect_key=f"ok:{lease.step_id}",
        output_refs=(),
        state={},
        now=NOW,
    )

    projection = kernel.get(run.id)
    assert checkpoint is None
    assert projection.status is RunStatus.CANCELLED
    assert projection.outcome is RunOutcome.CANCELLED
    assert {step.status for step in projection.steps} == {RunStatus.CANCELLED}
    assert kernel.lease_next("worker", NOW, timedelta(minutes=5), run_id=run.id) is None


@pytest.mark.integration
def test_expired_lease_reconciliation_finishes_cancelling_run(engine: Engine) -> None:
    kernel = ResearchRunKernel(engine)
    run = kernel.create(command("w1"), "cancel-restart-expired")
    lease = kernel.lease_next("worker", NOW, timedelta(minutes=1), run_id=run.id)
    assert lease is not None
    kernel.request_cancel(run.id, NOW)

    assert kernel.reconcile_startup(NOW + timedelta(minutes=2)) == 1
    projection = kernel.get(run.id)
    assert projection.status is RunStatus.CANCELLED
    assert projection.outcome is RunOutcome.CANCELLED
    assert {step.status for step in projection.steps} == {RunStatus.CANCELLED}


@pytest.mark.integration
def test_cancellation_waits_for_every_active_lease_boundary(engine: Engine) -> None:
    kernel = ResearchRunKernel(engine)
    run = kernel.create(command("w1", "w2"), "cancel-two-active")
    first = kernel.lease_next("worker-a", NOW, timedelta(minutes=5), run_id=run.id)
    second = kernel.lease_next("worker-b", NOW, timedelta(minutes=5), run_id=run.id)
    assert first is not None and second is not None
    assert first.target_id != second.target_id
    kernel.request_cancel(run.id, NOW)

    assert (
        kernel.checkpoint_success(
            first,
            effect_key=f"ok:{first.step_id}",
            output_refs=(),
            state={},
            now=NOW,
        )
        is None
    )
    halfway = kernel.get(run.id)
    assert halfway.status is RunStatus.CANCELLING
    assert sum(step.status is RunStatus.RUNNING for step in halfway.steps) == 1

    assert (
        kernel.checkpoint_success(
            second,
            effect_key=f"ok:{second.step_id}",
            output_refs=(),
            state={},
            now=NOW,
        )
        is None
    )
    cancelled = kernel.get(run.id)
    assert cancelled.status is RunStatus.CANCELLED
    assert {step.status for step in cancelled.steps} == {RunStatus.CANCELLED}


@pytest.mark.integration
def test_retry_has_due_time_bound_and_inspectable_terminal_failure(
    engine: Engine,
) -> None:
    kernel = ResearchRunKernel(engine)
    run = kernel.create(command("w1"), "retry-run")
    first = kernel.lease_next("worker", NOW, timedelta(minutes=5), run_id=run.id)
    assert first is not None
    due = NOW + timedelta(minutes=1)
    kernel.checkpoint_failure(
        first, "rate_limit", retryable=True, retry_at=due, now=NOW
    )
    assert kernel.lease_next("worker", NOW, timedelta(minutes=5), run_id=run.id) is None
    second = kernel.lease_next("worker", due, timedelta(minutes=5), run_id=run.id)
    assert second is not None and second.attempt_number == 2
    with pytest.raises(RetryLimitError):
        kernel.checkpoint_failure(
            second,
            "still rate limited",
            retryable=True,
            retry_at=due + timedelta(minutes=1),
            now=due,
        )
    projection = kernel.get(run.id)
    assert projection.status is RunStatus.FAILED
    assert projection.steps[0].error == "still rate limited"
    assert [attempt.attempt_number for attempt in projection.steps[0].attempts] == [
        1,
        2,
    ]
    assert projection.steps[0].attempts[-1].error == "still rate limited"
    with Session(engine) as session:
        attempts = session.scalars(
            select(StepAttempt).where(StepAttempt.step_id == second.step_id)
        ).all()
    assert [attempt.status for attempt in attempts] == ["FAILED", "FAILED"]


@pytest.mark.integration
def test_manual_retry_reactivates_cancelled_downstream_steps(engine: Engine) -> None:
    kernel = ResearchRunKernel(engine)
    run = kernel.create(command("w1"), "manual-retry")
    first = kernel.lease_next("worker", NOW, timedelta(minutes=5), run_id=run.id)
    assert first is not None
    kernel.checkpoint_failure(
        first,
        "operator-fixable",
        retryable=False,
        retry_at=None,
        now=NOW,
    )
    assert kernel.get(run.id).status is RunStatus.FAILED

    retried = kernel.retry(run.id, NOW + timedelta(seconds=1))
    assert retried.status is RunStatus.WAITING_RETRY
    assert retried.targets[0].outcome is None
    assert all(
        step.status in {RunStatus.WAITING_RETRY, RunStatus.PENDING}
        for step in retried.steps
    )

    retry_lease = kernel.lease_next(
        "worker", NOW + timedelta(seconds=1), timedelta(minutes=5), run_id=run.id
    )
    assert retry_lease is not None
    assert retry_lease.step_id == first.step_id
    kernel.checkpoint_success(
        retry_lease,
        effect_key=f"ok:{retry_lease.step_id}",
        output_refs=(),
        state={},
        now=NOW + timedelta(seconds=1),
    )
    next_lease = kernel.lease_next(
        "worker", NOW + timedelta(seconds=2), timedelta(minutes=5), run_id=run.id
    )
    assert next_lease is not None
    assert next_lease.kind is StepKind.PLAN


@pytest.mark.integration
def test_manual_retry_reactivates_every_failed_target_and_partial_run(
    engine: Engine,
) -> None:
    kernel = ResearchRunKernel(engine)
    run = kernel.create(command("w1", "w2"), "retry-all-targets")
    for _ in range(2):
        lease = kernel.lease_next("worker", NOW, timedelta(minutes=5), run_id=run.id)
        assert lease is not None
        kernel.checkpoint_failure(
            lease, "fixable", retryable=False, retry_at=None, now=NOW
        )
    assert kernel.get(run.id).status is RunStatus.FAILED
    retried = kernel.retry(run.id, NOW + timedelta(seconds=1))
    assert {target.outcome for target in retried.targets} == {None}
    assert sum(step.status is RunStatus.WAITING_RETRY for step in retried.steps) == 2

    partial = kernel.create(command("w1", "w2"), "retry-partial-run")
    with Session(engine) as session, session.begin():
        row = session.get(Run, partial.id)
        assert row is not None
        row.status = RunStatus.SUCCEEDED.value
        row.outcome = RunOutcome.PARTIAL.value
        partial_target = session.scalars(
            select(RunTarget).where(RunTarget.run_id == partial.id)
        ).first()
        assert partial_target is not None
        partial_target_id = partial_target.id
        partial_target.outcome = RunOutcome.PARTIAL.value
        for target in session.scalars(
            select(RunTarget).where(RunTarget.run_id == partial.id)
        ):
            if target.id != partial_target.id:
                target.outcome = RunOutcome.COMPLETE.value
        session.query(RunStep).filter(RunStep.run_id == partial.id).update(
            {RunStep.status: RunStatus.SUCCEEDED.value}
        )
    partial_retry = kernel.retry(partial.id, NOW + timedelta(seconds=2))
    assert partial_retry.status is RunStatus.WAITING_RETRY
    assert (
        next(
            target for target in partial_retry.targets if target.id == partial_target_id
        ).outcome
        is None
    )
    assert any(step.status is RunStatus.PENDING for step in partial_retry.steps)
