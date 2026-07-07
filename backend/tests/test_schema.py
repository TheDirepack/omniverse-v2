import pytest
from app.db.schema import (
    AgentRouteFallback,
    Anomaly,
    ExecutionState,
    ModelConfig,
    ProviderConfig,
    ProviderKey,
    Setting,
    TierSystem,
    Universe,
    WorldTier,
)
from sqlalchemy.exc import IntegrityError
from sqlmodel import select


class TestUniverse:
    def test_create(self, ephemeral_db):
        u = Universe(name="Marvel", summary="Earth-616")
        ephemeral_db.add(u)
        ephemeral_db.commit()

        row = ephemeral_db.exec(
            select(Universe).where(Universe.name == "Marvel")
        ).first()
        assert row is not None
        assert row.summary == "Earth-616"
        assert row.is_explored is False

    def test_name_empty(self, ephemeral_db):
        u = Universe(name="")
        ephemeral_db.add(u)
        ephemeral_db.commit()

    def test_name_very_long(self, ephemeral_db):
        long_name = "A" * 500
        u = Universe(name=long_name)
        ephemeral_db.add(u)
        ephemeral_db.commit()
        row = ephemeral_db.exec(
            select(Universe).where(Universe.name == long_name)
        ).first()
        assert row is not None

    def test_name_duplicates_allowed(self, ephemeral_db):
        ephemeral_db.add(Universe(name="SharedName"))
        ephemeral_db.commit()
        ephemeral_db.add(Universe(name="SharedName"))
        ephemeral_db.commit()
        rows = ephemeral_db.exec(
            select(Universe).where(Universe.name == "SharedName")
        ).all()
        assert len(rows) == 2

    def test_summary_none(self, ephemeral_db):
        u = Universe(name="NoSummary")
        ephemeral_db.add(u)
        ephemeral_db.commit()
        row = ephemeral_db.exec(
            select(Universe).where(Universe.name == "NoSummary")
        ).first()
        assert row.summary is None

    def test_summary_very_long(self, ephemeral_db):
        u = Universe(name="LongSummary", summary="A" * 100_000)
        ephemeral_db.add(u)
        ephemeral_db.commit()
        row = ephemeral_db.exec(
            select(Universe).where(Universe.name == "LongSummary")
        ).first()
        assert len(row.summary) == 100_000

    def test_is_explored_true(self, ephemeral_db):
        u = Universe(name="Explored", is_explored=True)
        ephemeral_db.add(u)
        ephemeral_db.commit()
        row = ephemeral_db.exec(
            select(Universe).where(Universe.name == "Explored")
        ).first()
        assert row.is_explored is True

    def test_is_explored_false_default(self, ephemeral_db):
        u = Universe(name="Default")
        ephemeral_db.add(u)
        ephemeral_db.commit()
        row = ephemeral_db.exec(
            select(Universe).where(Universe.name == "Default")
        ).first()
        assert row.is_explored is False

    def test_name_not_null_violation(self, ephemeral_db):
        u = Universe(name=None)
        ephemeral_db.add(u)
        with pytest.raises(IntegrityError):
            ephemeral_db.commit()


class TestSetting:
    def test_create(self, ephemeral_db):
        s = Setting(key="test_key", value="test_val")
        ephemeral_db.add(s)
        ephemeral_db.commit()
        row = ephemeral_db.get(Setting, "test_key")
        assert row.value == "test_val"

    def test_key_empty(self, ephemeral_db):
        s = Setting(key="", value="empty")
        ephemeral_db.add(s)
        ephemeral_db.commit()
        row = ephemeral_db.get(Setting, "")
        assert row.value == "empty"

    def test_key_duplicate_pk(self, ephemeral_db):
        ephemeral_db.add(Setting(key="dup", value="v1"))
        ephemeral_db.commit()
        ephemeral_db.merge(Setting(key="dup", value="v2"))
        ephemeral_db.commit()
        row = ephemeral_db.get(Setting, "dup")
        assert row.value == "v2"

    def test_value_none(self, ephemeral_db):
        s = Setting(key="nullable")
        ephemeral_db.add(s)
        ephemeral_db.commit()
        row = ephemeral_db.get(Setting, "nullable")
        assert row.value is None


class TestProviderConfig:
    def test_missing_name(self, ephemeral_db):
        p = ProviderConfig(name=None)
        ephemeral_db.add(p)
        with pytest.raises(IntegrityError):
            ephemeral_db.commit()

    def test_duplicate_name(self, ephemeral_db):
        ephemeral_db.add(ProviderConfig(name="same"))
        ephemeral_db.commit()
        ephemeral_db.add(ProviderConfig(name="same"))
        ephemeral_db.commit()
        rows = ephemeral_db.exec(
            select(ProviderConfig).where(ProviderConfig.name == "same")
        ).all()
        assert len(rows) == 2

    def test_all_optional_null(self, ephemeral_db):
        p = ProviderConfig(name="minimal")
        ephemeral_db.add(p)
        ephemeral_db.commit()
        row = ephemeral_db.exec(
            select(ProviderConfig).where(ProviderConfig.name == "minimal")
        ).first()
        assert row.provider_type is None
        assert row.base_url is None
        assert row.models is None


class TestProviderKey:
    def test_create(self, ephemeral_db):
        p = ProviderConfig(name="key-owner")
        ephemeral_db.add(p)
        ephemeral_db.commit()
        ephemeral_db.refresh(p)

        k = ProviderKey(provider_id=p.id, api_key="sk-test", priority=0)
        ephemeral_db.add(k)
        ephemeral_db.commit()
        row = ephemeral_db.exec(
            select(ProviderKey).where(ProviderKey.provider_id == p.id)
        ).first()
        assert row.api_key == "sk-test"

    def test_nonexistent_provider_fk(self, ephemeral_db):
        k = ProviderKey(provider_id=9999, api_key="sk-test")
        ephemeral_db.add(k)
        with pytest.raises(IntegrityError):
            ephemeral_db.commit()

    def test_priority_default(self, ephemeral_db):
        p = ProviderConfig(name="default-pri")
        ephemeral_db.add(p)
        ephemeral_db.commit()
        ephemeral_db.refresh(p)

        k = ProviderKey(provider_id=p.id, api_key="sk-test")
        ephemeral_db.add(k)
        ephemeral_db.commit()
        row = ephemeral_db.exec(
            select(ProviderKey).where(ProviderKey.provider_id == p.id)
        ).first()
        assert row.priority == 0


class TestAgentRouteFallback:
    def test_empty_task_type(self, ephemeral_db):
        from sqlmodel import select

        r = AgentRouteFallback(task_type="", priority=0)
        ephemeral_db.add(r)
        ephemeral_db.commit()
        row = ephemeral_db.exec(
            select(AgentRouteFallback).where(AgentRouteFallback.task_type == "")
        ).first()
        assert row is not None

    def test_provider_id_none(self, ephemeral_db):
        from sqlmodel import select

        r = AgentRouteFallback(task_type="TEST", priority=0, provider_id=None)
        ephemeral_db.add(r)
        ephemeral_db.commit()
        row = ephemeral_db.exec(
            select(AgentRouteFallback).where(AgentRouteFallback.task_type == "TEST")
        ).first()
        assert row.provider_id is None

    def test_provider_id_nonexistent_fk(self, ephemeral_db):
        r = AgentRouteFallback(task_type="BAD_FK", priority=0, provider_id=9999)
        ephemeral_db.add(r)
        with pytest.raises(IntegrityError):
            ephemeral_db.commit()

    def test_multiple_fallback_rows_per_task_type(self, ephemeral_db):
        # AgentRouteFallback intentionally allows multiple priority-ordered
        # rows per task_type (a fallback chain), unlike the old single-row
        # AgentRoute keyed by task_type.
        ephemeral_db.add(AgentRouteFallback(task_type="CHAIN", priority=0, models="v1"))
        ephemeral_db.add(AgentRouteFallback(task_type="CHAIN", priority=1, models="v2"))
        ephemeral_db.commit()
        rows = ephemeral_db.exec(
            select(AgentRouteFallback)
            .where(AgentRouteFallback.task_type == "CHAIN")
            .order_by(AgentRouteFallback.priority)
        ).all()
        assert len(rows) == 2
        assert rows[0].models == "v1"
        assert rows[1].models == "v2"


class TestTierSystem:
    def test_very_long_definition(self, ephemeral_db):
        ts = TierSystem(system_definition="A" * 100_000)
        ephemeral_db.add(ts)
        ephemeral_db.commit()
        row = ephemeral_db.exec(select(TierSystem)).first()
        assert len(row.system_definition) == 100_000


class TestWorldTier:
    def test_tier_number_below_range(self, seeded_db):
        ephemeral_db, u, _p, _r = seeded_db
        ts = TierSystem(system_definition="test system")
        ephemeral_db.add(ts)
        ephemeral_db.commit()
        ephemeral_db.refresh(ts)

        wt = WorldTier(
            universe_id=u.id,
            system_id=ts.id,
            tier_number=-1,
            justification="below range",
        )
        ephemeral_db.add(wt)
        ephemeral_db.commit()
        assert wt.tier_number == -1

    def test_tier_number_above_range(self, seeded_db):
        ephemeral_db, _u, _p, _r = seeded_db
        ts = TierSystem(system_definition="test system")
        ephemeral_db.add(ts)
        ephemeral_db.commit()
        ephemeral_db.refresh(ts)

        u2 = Universe(name="Second Universe")
        ephemeral_db.add(u2)
        ephemeral_db.commit()
        ephemeral_db.refresh(u2)

        wt = WorldTier(
            universe_id=u2.id,
            system_id=ts.id,
            tier_number=999,
            justification="above range",
        )
        ephemeral_db.add(wt)
        ephemeral_db.commit()
        assert wt.tier_number == 999

    def test_nonexistent_universe_fk(self, seeded_db):
        ephemeral_db, _u, _p, _r = seeded_db
        ts = TierSystem(system_definition="sys")
        ephemeral_db.add(ts)
        ephemeral_db.commit()
        ephemeral_db.refresh(ts)

        wt = WorldTier(
            universe_id=9999,
            system_id=ts.id,
            tier_number=5,
            justification="bad fk",
        )
        ephemeral_db.add(wt)
        with pytest.raises(IntegrityError):
            ephemeral_db.commit()

    def test_nonexistent_system_fk(self, seeded_db):
        ephemeral_db, u, _p, _r = seeded_db
        wt = WorldTier(
            universe_id=u.id, system_id=9999, tier_number=5, justification="bad fk"
        )
        ephemeral_db.add(wt)
        with pytest.raises(IntegrityError):
            ephemeral_db.commit()


class TestAnomaly:
    def test_universe_id_none(self, ephemeral_db):
        a = Anomaly(universe_id=None, description="no universe")
        ephemeral_db.add(a)
        with pytest.raises(IntegrityError):
            ephemeral_db.commit()

    def test_nonexistent_fk(self, ephemeral_db):
        a = Anomaly(universe_id=9999, description="bad fk")
        ephemeral_db.add(a)
        with pytest.raises(IntegrityError):
            ephemeral_db.commit()

    def test_empty_description(self, ephemeral_db):
        a = Anomaly(universe_id=None, description="")
        ephemeral_db.add(a)
        with pytest.raises(IntegrityError):
            ephemeral_db.commit()


class TestExecutionState:
    def test_empty_run_id(self, ephemeral_db):
        es = ExecutionState(
            run_id="",
            node_name="N",
            thought="T",
            status="S",
            state_snapshot="{}",
        )
        ephemeral_db.add(es)
        ephemeral_db.commit()

    def test_free_text_status(self, ephemeral_db):
        for status in [
            "IN_PROGRESS",
            "COMPLETED",
            "FAILED",
            "ABORT_REQUESTED",
            "ANYTHING",
        ]:
            es = ExecutionState(
                run_id="r",
                node_name="N",
                thought="T",
                status=status,
                state_snapshot="{}",
            )
            ephemeral_db.add(es)
        ephemeral_db.commit()
        rows = ephemeral_db.exec(select(ExecutionState)).all()
        assert len(rows) == 5

    def test_very_long_fields(self, ephemeral_db):
        es = ExecutionState(
            run_id="A" * 1000,
            node_name="B" * 1000,
            thought="C" * 100_000,
            status="D" * 1000,
            state_snapshot="E" * 100_000,
        )
        ephemeral_db.add(es)
        ephemeral_db.commit()
        row = ephemeral_db.exec(select(ExecutionState)).first()
        assert len(row.run_id) == 1000
        assert len(row.thought) == 100_000


class TestModelConfig:
    def test_nonexistent_provider_fk(self, ephemeral_db):
        mc = ModelConfig(model_name="gpt-4", provider_id=9999)
        ephemeral_db.add(mc)
        with pytest.raises(IntegrityError):
            ephemeral_db.commit()
