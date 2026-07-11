import pytest
from sqlmodel import select

from app.db.schema import Artifact, ArtifactRelation
from app.services.universe_service import UniverseService


@pytest.mark.slow
def test_import_all_from_registry_real_file(ephemeral_db):
    """Integration test using the actual default_worlds.json file."""
    svc = UniverseService(session=ephemeral_db)
    imported, _ = svc.import_all_from_registry()

    assert imported > 0
    # We should have at least Pokémon in the registry
    pokemon = svc.get_universe("Pokémon")
    assert pokemon is not None
    assert pokemon.slug == "pokemon"

    # Verify hierarchy
    gen1 = svc.get_universe("Red/Blue/Yellow")
    assert gen1 is not None
    assert gen1.parent_id == pokemon.id

@pytest.mark.slow
def test_import_single_world_real_file(ephemeral_db):
    """Integration test importing a specific world from the real registry."""
    svc = UniverseService(session=ephemeral_db)
    u = svc.import_from_registry("pokemon")
    assert u is not None
    assert u.name == "Pokémon"

@pytest.mark.slow
def test_merge_worlds_integration(ephemeral_db):
    """Test merging two universes with claims and entities."""
    svc = UniverseService(session=ephemeral_db)
    u1 = svc.create_universe(name="Verse A")
    u2 = svc.create_universe(name="Verse B")

    # Setup entities and claims in u2
    e_u2 = Artifact(name="EntityB", type="entity", universe_id=u2.id)
    ephemeral_db.add(e_u2)
    ephemeral_db.commit()
    ephemeral_db.refresh(e_u2)

    lit_u2 = Artifact(name="Something", type="literal", universe_id=u2.id)
    ephemeral_db.add(lit_u2)
    ephemeral_db.flush()
    c_u2 = ArtifactRelation(
        universe_id=u2.id, from_artifact_id=e_u2.id,
        to_artifact_id=lit_u2.id, relation_type="is_a"
    )
    ephemeral_db.add(c_u2)
    ephemeral_db.commit()

    # Merge B into A
    result = svc.merge_worlds(u1.id, u2.id)
    assert result["status"] == "success"

    # Verify EntityB moved to Verse A
    moved_e = ephemeral_db.exec(
        select(Artifact).where(Artifact.type == 'entity', Artifact.name == "EntityB")
    ).first()
    assert moved_e.universe_id == u1.id

    # Verify Claim moved to Verse A
    lit = ephemeral_db.exec(
        select(Artifact).where(Artifact.name == "Something")
    ).first()
    moved_c = ephemeral_db.exec(
        select(ArtifactRelation).where(ArtifactRelation.to_artifact_id == lit.id)
    ).first()
    assert moved_c.universe_id == u1.id

    # Verify u2 is deleted
    assert svc.get_universe_by_id(u2.id) is None
