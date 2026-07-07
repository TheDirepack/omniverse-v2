import pytest
from app.db.schema import Claim, Entity
from app.services.universe_service import UniverseService
from sqlmodel import select

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
    e_u2 = Entity(name="EntityB", entity_type="TypeB", universe_id=u2.id)
    ephemeral_db.add(e_u2)
    ephemeral_db.commit()
    ephemeral_db.refresh(e_u2)

    c_u2 = Claim(subject_id=e_u2.id, predicate="is_a", object_literal="Something", universe_scope=u2.id, status="VERIFIED")
    ephemeral_db.add(c_u2)
    ephemeral_db.commit()

    # Merge B into A
    result = svc.merge_worlds(u1.id, u2.id)
    assert result["status"] == "success"

    # Verify EntityB moved to Verse A
    moved_e = ephemeral_db.exec(select(Entity).where(Entity.name == "EntityB")).first()
    assert moved_e.universe_id == u1.id

    # Verify Claim moved to Verse A
    moved_c = ephemeral_db.exec(select(Claim).where(Claim.object_literal == "Something")).first()
    assert moved_c.universe_scope == u1.id

    # Verify u2 is deleted
    assert svc.get_universe_by_id(u2.id) is None
