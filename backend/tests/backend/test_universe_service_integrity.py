from sqlmodel import select

from app.db.schema import (
    Artifact,
    ArtifactRelation,
    Evidence,
    EvidenceChunk,
    Universe,
    UniverseRelation,
    WorldTier,
)
from app.services.universe_service import UniverseService


def test_delete_universe_cascading_cleanup(ephemeral_db):
    """Verify that deleting a universe cleans up all associated records
    to avoid IntegrityError."""
    session = ephemeral_db
    svc = UniverseService(session=session)

    # 1. Setup: Create a universe with all types of children
    u = Universe(name="IntegrityTestWorld", franchise="Test")
    session.add(u)
    session.commit()
    session.refresh(u)

    e = Artifact(name="TestEntity", type="entity", universe_id=u.id)
    session.add(e)
    session.commit()
    session.refresh(e)

    lit = Artifact(name="val", type="literal", universe_id=u.id)
    session.add(lit)
    session.flush()
    c = ArtifactRelation(
        universe_id=u.id,
        from_artifact_id=e.id,
        to_artifact_id=lit.id,
        relation_type="test",
    )
    session.add(c)

    ev = Evidence(universe_id=u.id, source_url="http://test.com")
    session.add(ev)
    session.commit()
    session.refresh(ev)

    ec = EvidenceChunk(evidence_id=ev.id, content="test content", chunk_index=0)
    session.add(ec)

    wt = WorldTier(universe_id=u.id, system_id=1, tier_number=1, justification="test")
    # Note: We might need a TierSystem for the FK to work,
    # let's assume one exists or create one
    from app.db.schema import TierSystem
    ts = TierSystem(system_definition="test")
    session.add(ts)
    session.commit()
    wt.system_id = ts.id
    session.add(wt)

    rel = UniverseRelation(
        from_universe_id=u.id,
        to_universe_id=u.id,
        relation_type="SELF",
    )
    session.add(rel)

    session.commit()

    # 2. Execution: Delete the universe
    # This should not raise IntegrityError
    svc.delete_universe(u.id)

    # 3. Verification: Ensure all records are gone
    assert session.get(Universe, u.id) is None
    assert session.exec(
        select(Artifact).where(Artifact.type == 'entity', Artifact.universe_id == u.id)
    ).first() is None
    assert session.exec(
        select(ArtifactRelation).where(ArtifactRelation.universe_id == u.id)
    ).first() is None
    assert session.exec(
        select(Evidence).where(Evidence.universe_id == u.id)
    ).first() is None
    assert session.exec(
        select(EvidenceChunk).where(EvidenceChunk.evidence_id == ev.id)
    ).first() is None
    assert session.exec(
        select(WorldTier).where(WorldTier.universe_id == u.id)
    ).first() is None
    assert session.exec(
        select(UniverseRelation).where(
            (UniverseRelation.from_universe_id == u.id) |
            (UniverseRelation.to_universe_id == u.id)
        )
    ).first() is None

def test_merge_worlds_cascading_reassignment(ephemeral_db):
    """Verify that merging a universe moves all associated records to
    the kept universe."""
    session = ephemeral_db
    svc = UniverseService(session=session)

    # Setup two universes
    u_keep = Universe(name="KeepWorld", franchise="Keep")
    u_merge = Universe(name="MergeWorld", franchise="Merge")
    session.add_all([u_keep, u_merge])
    session.commit()
    session.refresh(u_keep)
    session.refresh(u_merge)

    # Add children to MergeWorld
    e_merge = Artifact(name="MergeEntity", type="entity", universe_id=u_merge.id)
    session.add(e_merge)
    session.commit()
    session.refresh(e_merge)

    lit_merge = Artifact(name="val", type="literal", universe_id=u_merge.id)
    session.add(lit_merge)
    session.flush()
    c_merge = ArtifactRelation(
        universe_id=u_merge.id,
        from_artifact_id=e_merge.id,
        to_artifact_id=lit_merge.id,
        relation_type="test",
    )
    session.add(c_merge)

    ev_merge = Evidence(universe_id=u_merge.id, source_url="http://merge.com")
    session.add(ev_merge)
    session.commit()
    session.refresh(ev_merge)

    ec_merge = EvidenceChunk(
        evidence_id=ev_merge.id,
        content="merge content",
        chunk_index=0,
    )
    session.add(ec_merge)

    rel_merge = UniverseRelation(
        from_universe_id=u_merge.id,
        to_universe_id=u_keep.id,
        relation_type="PARENT",
    )
    session.add(rel_merge)

    session.commit()

    # Execute Merge
    svc.merge_worlds(u_keep.id, u_merge.id)

    # Verify reassignment
    assert session.get(Universe, u_merge.id) is None

    # Entity moved?
    assert session.exec(
        select(Artifact).where(
            Artifact.type == 'entity',
            Artifact.universe_id == u_keep.id,
            Artifact.name == "MergeEntity"
        )
    ).first() is not None
    # Claim moved?
    assert session.exec(
        select(ArtifactRelation).where(
            ArtifactRelation.universe_id == u_keep.id,
            ArtifactRelation.relation_type == "test"
        )
    ).first() is not None
    # Evidence moved?
    assert session.exec(
        select(Evidence).where(
            Evidence.universe_id == u_keep.id,
            Evidence.source_url == "http://merge.com"
        )
    ).first() is not None
    # Relation moved?
    assert session.exec(
        select(UniverseRelation).where(
            UniverseRelation.from_universe_id == u_keep.id,
            UniverseRelation.to_universe_id == u_keep.id
        )
    ).first() is not None
