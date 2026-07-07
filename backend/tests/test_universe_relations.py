from app.db.schema import Entity, Universe, UniverseRelation
from app.repositories.universe import UniverseRepository
from app.services.universe_service import UniverseService


def test_universe_relation_creation(ephemeral_db):
    # Setup
    u1 = Universe(name="Universe A")
    u2 = Universe(name="Universe B")
    ephemeral_db.add_all([u1, u2])
    ephemeral_db.commit()
    ephemeral_db.refresh(u1)
    ephemeral_db.refresh(u2)

    service = UniverseService(session=ephemeral_db)
    relation = service.create_universe_relation(
        from_id=u1.id, to_id=u2.id, rel_type="PRECEDES", description="A leads to B"
    )

    assert relation.id is not None
    assert relation.from_universe_id == u1.id
    assert relation.to_universe_id == u2.id
    assert relation.relation_type == "PRECEDES"
    assert relation.description == "A leads to B"


def test_get_relations_directions(ephemeral_db):
    # Setup
    u1 = Universe(name="U1")
    u2 = Universe(name="U2")
    u3 = Universe(name="U3")
    ephemeral_db.add_all([u1, u2, u3])
    ephemeral_db.commit()
    ephemeral_db.refresh(u1)
    ephemeral_db.refresh(u2)
    ephemeral_db.refresh(u3)

    repo = UniverseRepository(ephemeral_db)
    # U1 -> U2 (Out from U1, In to U2)
    repo.create_relation(
        UniverseRelation(
            from_universe_id=u1.id, to_universe_id=u2.id, relation_type="ALT"
        )
    )
    # U3 -> U1 (In to U1, Out from U3)
    repo.create_relation(
        UniverseRelation(
            from_universe_id=u3.id, to_universe_id=u1.id, relation_type="PRECEDES"
        )
    )

    # Test Out from U1: should only be U2
    out_rels = repo.get_relations(u1.id, direction="out")
    assert len(out_rels) == 1
    assert out_rels[0].to_universe_id == u2.id

    # Test In to U1: should only be U3
    in_rels = repo.get_relations(u1.id, direction="in")
    assert len(in_rels) == 1
    assert in_rels[0].from_universe_id == u3.id

    # Test Both for U1: should be U2 and U3
    both_rels = repo.get_relations(u1.id, direction="both")
    assert len(both_rels) == 2
    ids = {r.from_universe_id for r in both_rels} | {
        r.to_universe_id for r in both_rels
    }
    assert u1.id in ids
    assert u2.id in ids
    assert u3.id in ids


def test_get_related_universes(ephemeral_db):
    # Setup
    u1 = Universe(name="U1")
    u2 = Universe(name="U2")
    u3 = Universe(name="U3")
    ephemeral_db.add_all([u1, u2, u3])
    ephemeral_db.commit()
    ephemeral_db.refresh(u1)
    ephemeral_db.refresh(u2)
    ephemeral_db.refresh(u3)

    repo = UniverseRepository(ephemeral_db)
    repo.create_relation(
        UniverseRelation(
            from_universe_id=u1.id, to_universe_id=u2.id, relation_type="ALT"
        )
    )
    repo.create_relation(
        UniverseRelation(
            from_universe_id=u3.id, to_universe_id=u1.id, relation_type="PRECEDES"
        )
    )

    related = repo.get_related_universes(u1.id)
    names = {u.name for u in related}
    assert "U2" in names
    assert "U3" in names
    assert len(names) == 2


def test_entity_canonicalization(ephemeral_db):
    # Setup
    u1 = Universe(name="U1")
    u2 = Universe(name="U2")
    ephemeral_db.add_all([u1, u2])
    ephemeral_db.commit()
    ephemeral_db.refresh(u1)
    ephemeral_db.refresh(u2)

    # Entity in U1 (Canonical)
    e1 = Entity(name="Hero", entity_type="Person", universe_id=u1.id, canonical=True)
    ephemeral_db.add(e1)
    ephemeral_db.commit()
    ephemeral_db.refresh(e1)

    # Entity in U2 (Linked to e1)
    e2 = Entity(name="Hero", entity_type="Person", universe_id=u2.id, canonical=False)
    ephemeral_db.add(e2)
    ephemeral_db.commit()
    ephemeral_db.refresh(e2)

    repo = UniverseRepository(ephemeral_db)
    repo.set_entity_canonical(e2.id, e1.id)

    # Verify e2 is now linked to e1
    updated_e2 = ephemeral_db.get(Entity, e2.id)
    assert updated_e2.canonical_entity_id == e1.id
    assert updated_e2.canonical is False


def test_entity_mark_canonical(ephemeral_db):
    # Setup
    u1 = Universe(name="U1")
    ephemeral_db.add(u1)
    ephemeral_db.commit()
    ephemeral_db.refresh(u1)

    e1 = Entity(name="Hero", entity_type="Person", universe_id=u1.id)
    ephemeral_db.add(e1)
    ephemeral_db.commit()
    ephemeral_db.refresh(e1)

    repo = UniverseRepository(ephemeral_db)
    repo.set_entity_canonical(e1.id, None)

    updated_e1 = ephemeral_db.get(Entity, e1.id)
    assert updated_e1.canonical_entity_id is None
    assert updated_e1.canonical is True
