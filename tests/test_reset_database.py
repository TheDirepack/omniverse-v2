import pytest
from sqlmodel import Session, select
from app.db.session import engine
from app.db.unconfirmed_session import engine as unconfirmed_engine
from app.db.unconfirmed_schema import UnconfirmedUniverse, UnconfirmedTrait
from app.db.schema import Universe, Entity, EntityAlias, Claim, InferenceRule, InferredClaim


class TestResetDatabaseUnconfirmedFKOrdering:
    """Regression test for the actual bug reported: resetting the database
    raised a foreign-key IntegrityError against unconfirmed.db whenever any
    UnconfirmedTrait rows existed, because the reset deleted the parent
    (UnconfirmedUniverse) before the child (UnconfirmedTrait) while
    PRAGMA foreign_keys=ON is enabled on that engine."""

    ENDPOINT = "/api/worlds/reset-database"

    def test_reset_with_unconfirmed_trait_rows_does_not_raise(self, client):
        with Session(unconfirmed_engine) as session:
            u = UnconfirmedUniverse(name="TEST_Unconfirmed")
            session.add(u)
            session.commit()
            session.refresh(u)
            session.add(UnconfirmedTrait(universe_id=u.id, name="SomeTrait", value="SomeValue"))
            session.commit()

        # Before the fix, this raised sqlalchemy.exc.IntegrityError
        # (FOREIGN KEY constraint failed) instead of returning 200.
        r = client.post(self.ENDPOINT)
        assert r.status_code == 200
        assert r.json()["status"] == "success"

    def test_reset_actually_clears_unconfirmed_tables(self, client):
        with Session(unconfirmed_engine) as session:
            u = UnconfirmedUniverse(name="TEST_ClearMe")
            session.add(u)
            session.commit()
            session.refresh(u)
            session.add(UnconfirmedTrait(universe_id=u.id, name="T", value="V"))
            session.commit()

        r = client.post(self.ENDPOINT)
        assert r.status_code == 200

        with Session(unconfirmed_engine) as session:
            assert session.exec(select(UnconfirmedUniverse)).all() == []
            assert session.exec(select(UnconfirmedTrait)).all() == []

    def test_reset_with_multiple_traits_per_universe(self, client):
        """Multiple children referencing the same parent -- the exact shape
        that would have failed most reliably under the old ordering."""
        with Session(unconfirmed_engine) as session:
            u1 = UnconfirmedUniverse(name="TEST_MultiA")
            u2 = UnconfirmedUniverse(name="TEST_MultiB")
            session.add_all([u1, u2])
            session.commit()
            for u in [u1, u2]:
                session.refresh(u)
            session.add_all([
                UnconfirmedTrait(universe_id=u1.id, name="T1", value="V1"),
                UnconfirmedTrait(universe_id=u1.id, name="T2", value="V2"),
                UnconfirmedTrait(universe_id=u2.id, name="T3", value="V3"),
            ])
            session.commit()

        r = client.post(self.ENDPOINT)
        assert r.status_code == 200
        with Session(unconfirmed_engine) as session:
            assert session.exec(select(UnconfirmedUniverse)).all() == []
            assert session.exec(select(UnconfirmedTrait)).all() == []


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

        c1 = Claim(subject_id=a.id, predicate="USES", object_id=b.id)
        c2 = Claim(subject_id=b.id, predicate="GENERATES", object_id=c.id)
        db.add_all([c1, c2])
        db.commit()
        for c_ in [c1, c2]:
            db.refresh(c_)

        rule = InferenceRule(predicate_1="USES", predicate_2="GENERATES", implied_predicate="PRODUCES",
                              status="APPROVED", human_approved=True)
        db.add(rule)
        db.commit()
        db.refresh(rule)

        inferred = InferredClaim(
            subject_id=a.id, predicate="PRODUCES", object_id=c.id,
            derived_from_rule_id=rule.id, path_claim_ids="[1, 2]",
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
            assert session.exec(select(Entity)).all() == [], "Entity rows survived reset"
            assert session.exec(select(EntityAlias)).all() == [], "EntityAlias rows survived reset"
            assert session.exec(select(Claim)).all() == [], "Claim rows survived reset"
            assert session.exec(select(InferenceRule)).all() == [], "InferenceRule rows survived reset"
            assert session.exec(select(InferredClaim)).all() == [], "InferredClaim rows survived reset"

    def test_reset_does_not_orphan_entities_pointing_at_reset_universe(self, ephemeral_db, client):
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
            remaining_entities = session.exec(select(Entity).where(Entity.universe_id == u.id)).all()
            assert remaining_entities == []
