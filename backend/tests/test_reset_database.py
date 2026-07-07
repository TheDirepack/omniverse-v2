from app.db.schema import (
    Claim,
    Entity,
    EntityAlias,
    InferenceRule,
    InferredClaim,
    Universe,
)
from app.db.session import engine
from app.db.unconfirmed_schema import UnconfirmedUniverse
from app.db.unconfirmed_session import unconfirmed_engine
from sqlmodel import Session, select


class TestResetDatabaseInferenceTables:
    """Regression test: Entity/EntityAlias/Claim/InferenceRule/InferredClaim
    were missing entirely from the main-db reset pass, so they'd survive a
    'reset database' as orphaned rows pointing at deleted/reset universes."""

    ENDPOINT = "/api/worlds/reset-database"

    def _seed_full_inference_graph(self, db):
        u = Universe(name="TEST_ResetInference", is_explored=True)
        db.add(u)
        db.commit()
        db.refresh(u)

        a = Entity(name="A", entity_type="X", universe_id=u.id)
        b = Entity(name="B", entity_type="X", universe_id=u.id)
        c = Entity(name="C", entity_type="X", universe_id=u.id)
        db.add_all([a, b, c])
        db.commit()
        for e in [a, b, c]:
            db.refresh(e)

        alias = EntityAlias(entity_id=a.id, alias="Alt Name", universe_id=u.id)
        db.add(alias)
        db.commit()

        c1 = Claim(subject_id=a.id, predicate="USES", object_entity_id=b.id)
        c2 = Claim(subject_id=b.id, predicate="GENERATES", object_entity_id=c.id)
        db.add_all([c1, c2])
        db.commit()
        for c_ in [c1, c2]:
            db.refresh(c_)

        rule = InferenceRule(
            predicate_1="USES",
            predicate_2="GENERATES",
            implied_predicate="PRODUCES",
            status="APPROVED",
            human_approved=True,
        )

        db.add(rule)
        db.commit()
        db.refresh(rule)

        inferred = InferredClaim(
            subject_id=a.id,
            predicate="PRODUCES",
            object_id=c.id,
            derived_from_rule_id=rule.id,
        )
        db.add(inferred)
        db.commit()
        return u

    def test_reset_with_full_inference_graph_does_not_raise(self, ephemeral_db, client):
        """Before the fix, these tables weren't touched at all by reset, so
        this specifically checks the endpoint still succeeds (no FK issue
        surfaces here since nothing deletes them) -- the real assertion is
        in the next test, that they're actually gone afterward."""
        self._seed_full_inference_graph(ephemeral_db)
        r = client.post(self.ENDPOINT)
        assert r.status_code == 200

    def test_reset_actually_clears_all_new_inference_tables(self, ephemeral_db, client):
        self._seed_full_inference_graph(ephemeral_db)

        r = client.post(self.ENDPOINT)
        assert r.status_code == 200

        with Session(engine) as session:
            assert session.exec(select(Entity)).all() == [], (
                "Entity rows survived reset"
            )
            assert session.exec(select(EntityAlias)).all() == [], (
                "EntityAlias rows survived reset"
            )
            assert session.exec(select(Claim)).all() == [], "Claim rows survived reset"
            assert session.exec(select(InferenceRule)).all() == [], (
                "InferenceRule rows survived reset"
            )
            assert session.exec(select(InferredClaim)).all() == [], (
                "InferredClaim rows survived reset"
            )

    def test_reset_does_not_orphan_entities_pointing_at_reset_universe(
        self, ephemeral_db, client
    ):
        """Universes aren't deleted by reset (only cleared in place), but
        Entity rows referencing them must not be left dangling either way --
        confirms the fix clears the dependent graph regardless of what
        happens to the parent Universe row."""
        u = self._seed_full_inference_graph(ephemeral_db)

        r = client.post(self.ENDPOINT)
        assert r.status_code == 200

        with Session(engine) as session:
            # Universe itself persists (reset clears summary/explored flags,
            # doesn't delete the row) -- but nothing should still reference it.
            remaining_entities = session.exec(
                select(Entity).where(Entity.universe_id == u.id)
            ).all()
            assert remaining_entities == []
