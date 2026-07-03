import pytest
from sqlmodel import select
from app.db.schema import (
    Universe, Setting, ProviderConfig, AgentRoute,
    Trait, TierSystem, WorldTier, Anomaly, Theory,
    ExecutionState, ModelConfig
)


class TestUniverse:
    def test_create(self, ephemeral_db):
        u = Universe(name="Marvel", summary="Earth-616")
        ephemeral_db.add(u)
        ephemeral_db.commit()

        row = ephemeral_db.exec(select(Universe).where(Universe.name == "Marvel")).first()
        assert row is not None
        assert row.summary == "Earth-616"
        assert row.is_explored is False

    def test_name_empty(self, ephemeral_db):
        u = Universe(name="")
        ephemeral_db.add(u)
        ephemeral_db.commit()

    def test_name_duplicate(self, ephemeral_db):
        ephemeral_db.add(Universe(name="DC"))
        ephemeral_db.commit()
        with pytest.raises(Exception):
            ephemeral_db.add(Universe(name="DC"))
            ephemeral_db.commit()

    def test_name_very_long(self, ephemeral_db):
        long_name = "A" * 500
        u = Universe(name=long_name)
        ephemeral_db.add(u)
        ephemeral_db.commit()
        row = ephemeral_db.exec(select(Universe).where(Universe.name == long_name)).first()
        assert row is not None

    def test_name_unique_constraint(self, ephemeral_db):
        ephemeral_db.add(Universe(name="Unique"))
        ephemeral_db.commit()
        with pytest.raises(Exception):
            ephemeral_db.add(Universe(name="Unique"))
            ephemeral_db.commit()

    def test_summary_none(self, ephemeral_db):
        u = Universe(name="NoSummary")
        ephemeral_db.add(u)
        ephemeral_db.commit()
        row = ephemeral_db.exec(select(Universe).where(Universe.name == "NoSummary")).first()
        assert row.summary is None

    def test_summary_very_long(self, ephemeral_db):
        u = Universe(name="LongSummary", summary="A" * 100_000)
        ephemeral_db.add(u)
        ephemeral_db.commit()
        row = ephemeral_db.exec(select(Universe).where(Universe.name == "LongSummary")).first()
        assert len(row.summary) == 100_000

    def test_is_explored_true(self, ephemeral_db):
        u = Universe(name="Explored", is_explored=True)
        ephemeral_db.add(u)
        ephemeral_db.commit()
        row = ephemeral_db.exec(select(Universe).where(Universe.name == "Explored")).first()
        assert row.is_explored is True

    def test_is_explored_false_default(self, ephemeral_db):
        u = Universe(name="Default")
        ephemeral_db.add(u)
        ephemeral_db.commit()
        row = ephemeral_db.exec(select(Universe).where(Universe.name == "Default")).first()
        assert row.is_explored is False

    def test_name_not_null_violation(self, ephemeral_db):
        with pytest.raises(Exception):
            u = Universe(name=None)
            ephemeral_db.add(u)
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
        with pytest.raises(Exception):
            p = ProviderConfig(name=None)
            ephemeral_db.add(p)
            ephemeral_db.commit()

    def test_duplicate_name(self, ephemeral_db):
        ephemeral_db.add(ProviderConfig(name="same"))
        ephemeral_db.commit()
        ephemeral_db.add(ProviderConfig(name="same"))
        ephemeral_db.commit()
        rows = ephemeral_db.exec(select(ProviderConfig).where(ProviderConfig.name == "same")).all()
        assert len(rows) == 2

    def test_all_optional_null(self, ephemeral_db):
        p = ProviderConfig(name="minimal")
        ephemeral_db.add(p)
        ephemeral_db.commit()
        row = ephemeral_db.exec(select(ProviderConfig).where(ProviderConfig.name == "minimal")).first()
        assert row.provider_type is None
        assert row.api_key is None
        assert row.base_url is None
        assert row.models is None


class TestAgentRoute:
    def test_empty_task_type(self, ephemeral_db):
        r = AgentRoute(task_type="")
        ephemeral_db.add(r)
        ephemeral_db.commit()
        row = ephemeral_db.get(AgentRoute, "")
        assert row is not None

    def test_provider_id_none(self, ephemeral_db):
        r = AgentRoute(task_type="TEST", provider_id=None)
        ephemeral_db.add(r)
        ephemeral_db.commit()
        row = ephemeral_db.get(AgentRoute, "TEST")
        assert row.provider_id is None

    def test_provider_id_nonexistent_fk(self, ephemeral_db):
        r = AgentRoute(task_type="BAD_FK", provider_id=9999)
        with pytest.raises(Exception):
            ephemeral_db.add(r)
            ephemeral_db.commit()

    def test_duplicate_task_type_upsert(self, ephemeral_db):
        ephemeral_db.add(AgentRoute(task_type="UPSERT", model_name="v1"))
        ephemeral_db.commit()
        ephemeral_db.merge(AgentRoute(task_type="UPSERT", model_name="v2"))
        ephemeral_db.commit()
        row = ephemeral_db.get(AgentRoute, "UPSERT")
        assert row.model_name == "v2"


class TestTrait:
    def test_universe_id_required(self, ephemeral_db):
        with pytest.raises(Exception):
            t = Trait(universe_id=None, name="power", value="flight")
            ephemeral_db.add(t)
            ephemeral_db.commit()

    def test_nonexistent_fk(self, ephemeral_db):
        t = Trait(universe_id=9999, name="power", value="flight")
        with pytest.raises(Exception):
            ephemeral_db.add(t)
            ephemeral_db.commit()

    def test_empty_name(self, seeded_db):
        ephemeral_db, u, p, r = seeded_db
        t = Trait(universe_id=u.id, name="", value="val")
        ephemeral_db.add(t)
        ephemeral_db.commit()


class TestTierSystem:
    def test_very_long_definition(self, ephemeral_db):
        ts = TierSystem(system_definition="A" * 100_000)
        ephemeral_db.add(ts)
        ephemeral_db.commit()
        row = ephemeral_db.exec(select(TierSystem)).first()
        assert len(row.system_definition) == 100_000


class TestWorldTier:
    def test_tier_number_out_of_range(self, seeded_db):
        ephemeral_db, u, p, r = seeded_db
        ts = TierSystem(system_definition="test system")
        ephemeral_db.add(ts)
        ephemeral_db.commit()
        ephemeral_db.refresh(ts)

        wt = WorldTier(universe_id=u.id, system_id=ts.id, tier_number=-1, justification="below range")
        ephemeral_db.add(wt)
        ephemeral_db.commit()

        wt2 = WorldTier(universe_id=u.id, system_id=ts.id, tier_number=999, justification="above range")
        ephemeral_db.add(wt2)
        ephemeral_db.commit()

    def test_nonexistent_universe_fk(self, seeded_db):
        ephemeral_db, u, p, r = seeded_db
        ts = TierSystem(system_definition="sys")
        ephemeral_db.add(ts)
        ephemeral_db.commit()
        ephemeral_db.refresh(ts)

        wt = WorldTier(universe_id=9999, system_id=ts.id, tier_number=5, justification="bad fk")
        with pytest.raises(Exception):
            ephemeral_db.add(wt)
            ephemeral_db.commit()

    def test_nonexistent_system_fk(self, seeded_db):
        ephemeral_db, u, p, r = seeded_db
        wt = WorldTier(universe_id=u.id, system_id=9999, tier_number=5, justification="bad fk")
        with pytest.raises(Exception):
            ephemeral_db.add(wt)
            ephemeral_db.commit()


class TestAnomaly:
    def test_universe_id_none(self, ephemeral_db):
        a = Anomaly(universe_id=None, description="no universe")
        with pytest.raises(Exception):
            ephemeral_db.add(a)
            ephemeral_db.commit()

    def test_nonexistent_fk(self, ephemeral_db):
        a = Anomaly(universe_id=9999, description="bad fk")
        with pytest.raises(Exception):
            ephemeral_db.add(a)
            ephemeral_db.commit()

    def test_empty_description(self, ephemeral_db):
        a = Anomaly(universe_id=None, description="")
        with pytest.raises(Exception):
            ephemeral_db.add(a)
            ephemeral_db.commit()


class TestTheory:
    def test_nonexistent_fk(self, ephemeral_db):
        t = Theory(universe_id=9999, theory_text="content")
        with pytest.raises(Exception):
            ephemeral_db.add(t)
            ephemeral_db.commit()

    def test_empty_theory_text(self, seeded_db):
        ephemeral_db, u, p, r = seeded_db
        t = Theory(universe_id=u.id, theory_text="")
        ephemeral_db.add(t)
        ephemeral_db.commit()

    def test_auditor_feedback_none(self, seeded_db):
        ephemeral_db, u, p, r = seeded_db
        t = Theory(universe_id=u.id, theory_text="text")
        ephemeral_db.add(t)
        ephemeral_db.commit()
        row = ephemeral_db.exec(select(Theory)).first()
        assert row.auditor_feedback is None


class TestExecutionState:
    def test_empty_run_id(self, ephemeral_db):
        es = ExecutionState(run_id="", node_name="N", thought="T", status="S", state_snapshot="{}")
        ephemeral_db.add(es)
        ephemeral_db.commit()

    def test_free_text_status(self, ephemeral_db):
        for status in ["IN_PROGRESS", "COMPLETED", "FAILED", "ABORT_REQUESTED", "ANYTHING"]:
            es = ExecutionState(run_id="r", node_name="N", thought="T", status=status, state_snapshot="{}")
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
        with pytest.raises(Exception):
            ephemeral_db.add(mc)
            ephemeral_db.commit()
