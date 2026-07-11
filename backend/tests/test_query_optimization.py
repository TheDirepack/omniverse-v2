from app.db.schema import Artifact, ArtifactRelation, Universe
from app.repositories.inference import InferenceRepository
from app.repositories.universe import UniverseRepository


def test_universe_get_all_pagination(ephemeral_db):
    repo = UniverseRepository(ephemeral_db)
    # Setup 15 universes
    for i in range(15):
        u = Universe(name=f"U{i:02d}", summary=f"S{i}", slug=f"u{i}")
        ephemeral_db.add(u)
    ephemeral_db.commit()

    # Test limit
    res = repo.get_all(limit=5, offset=0)
    assert len(res) == 5

    # Test offset
    res_offset = repo.get_all(limit=5, offset=5)
    assert len(res_offset) == 5
    assert res[0].name != res_offset[0].name

def test_universe_get_all_projection(ephemeral_db):
    repo = UniverseRepository(ephemeral_db)
    u = Universe(name="Test", summary="Summ", slug="test")
    ephemeral_db.add(u)
    ephemeral_db.commit()

    # Test field projection
    res = repo.get_all(fields=["name"])
    assert len(res) == 1
    row = res[0]
    val = (
        row[0] if isinstance(row, tuple)
        else (row.name if hasattr(row, "name") else row)
    )
    assert val == "Test"

def test_inference_get_claims_by_predicate_pagination(ephemeral_db):
    repo = InferenceRepository(ephemeral_db)

    # Setup Universe
    u = Universe(name="TestU", summary="S", slug="testu")
    ephemeral_db.add(u)
    ephemeral_db.commit()

    # Setup Entities
    e1 = Artifact(name="E1", type="entity", universe_id=u.id)
    ephemeral_db.add(e1)
    ephemeral_db.commit()

    # Setup 15 unique claims by using different object entities
    for i in range(15):
        e_obj = Artifact(name=f"Obj{i}", type="entity", universe_id=u.id)
        ephemeral_db.add(e_obj)
        ephemeral_db.commit()
        c = ArtifactRelation(
            universe_id=u.id,
            from_artifact_id=e1.id,
            to_artifact_id=e_obj.id,
            relation_type="TEST_PRED",
        )
        ephemeral_db.add(c)
    ephemeral_db.commit()

    # Test limit
    res = repo.get_claims_by_predicate(predicate="TEST_PRED", limit=5, offset=0)
    assert len(res) == 5

    # Test offset
    res_offset = repo.get_claims_by_predicate(predicate="TEST_PRED", limit=5, offset=5)
    assert len(res_offset) == 5
    assert len(res) == len(res_offset)

def test_inference_get_claims_by_predicate_projection(ephemeral_db):
    repo = InferenceRepository(ephemeral_db)

    # Setup Universe
    u = Universe(name="TestU", summary="S", slug="testu")
    ephemeral_db.add(u)
    ephemeral_db.commit()

    e1 = Artifact(name="E1", type="entity", universe_id=u.id)
    e2 = Artifact(name="E2", type="entity", universe_id=u.id)
    ephemeral_db.add_all([e1, e2])
    ephemeral_db.commit()

    c = ArtifactRelation(
        universe_id=u.id,
        from_artifact_id=e1.id,
        to_artifact_id=e2.id,
        relation_type="TEST_PRED",
    )
    ephemeral_db.add(c)
    ephemeral_db.commit()

    res = repo.get_claims_by_predicate(predicate="TEST_PRED", fields=["subject_id"])
    assert len(res) == 1
    row = res[0]
    val = row[0] if isinstance(row, tuple) else row
    assert val == e1.id
