import pytest
from sqlmodel import Session, select
from app.db.schema import Universe, TierSystem
from app.services.universe_service import UniverseService

def test_filter_universes_query(ephemeral_db):
    session = ephemeral_db
    svc = UniverseService(session=session)
    
    u1 = svc.create_universe(name="Marvel Cinematic Universe", franchise="Marvel")
    u2 = svc.create_universe(name="DC Extended Universe", franchise="DC")
    u3 = svc.create_universe(name="Star Wars", franchise="Lucasfilm")
    
    # Test query by name
    filtered = svc.filter_universes(q="Marvel")
    assert len(filtered) == 1
    assert filtered[0].name == "Marvel Cinematic Universe"
    
    # Test query by franchise
    filtered = svc.filter_universes(q="DC")
    assert len(filtered) == 1
    assert filtered[0].name == "DC Extended Universe"
    
    # Test query by common term
    filtered = svc.filter_universes(q="Universe")
    assert len(filtered) == 2

def test_filter_universes_explored(ephemeral_db):
    session = ephemeral_db
    svc = UniverseService(session=session)
    
    u1 = svc.create_universe(name="World 1")
    u1.is_explored = True
    u2 = svc.create_universe(name="World 2")
    u2.is_explored = False
    session.add_all([u1, u2])
    session.commit()
    
    # Test explored=yes
    filtered = svc.filter_universes(explored="yes")
    assert len(filtered) == 1
    assert filtered[0].name == "World 1"
    
    # Test explored=no
    filtered = svc.filter_universes(explored="no")
    assert len(filtered) == 1
    assert filtered[0].name == "World 2"

def test_filter_universes_franchise(ephemeral_db):
    session = ephemeral_db
    svc = UniverseService(session=session)
    
    u1 = svc.create_universe(name="World 1", franchise="Marvel")
    u2 = svc.create_universe(name="World 2", franchise="DC")
    
    # Test franchise filter
    filtered = svc.filter_universes(franchise="Marvel")
    assert len(filtered) == 1
    assert filtered[0].name == "World 1"

def test_find_duplicates(ephemeral_db):
    session = ephemeral_db
    svc = UniverseService(session=session)
    
    u1 = Universe(name="Marvel Cinematic Universe", slug="mcu")
    u2 = Universe(name="Marvel Cinematic Universe (Alternative)", slug="mcu_alt")
    u3 = Universe(name="DC Extended Universe", slug="dceu")
    session.add_all([u1, u2, u3])
    session.commit()
    
    # Exact match
    dupes = svc.find_duplicates("Marvel Cinematic Universe")
    assert len(dupes) >= 1
    assert dupes[0]["name"] == "Marvel Cinematic Universe"
    assert dupes[0]["similarity"] == 1.0
    
    # Partial match
    dupes = svc.find_duplicates("Marvel Cinematic")
    assert len(dupes) >= 2
    
    # No match
    dupes = svc.find_duplicates("Something Completely Different")
    assert len(dupes) == 0

def test_import_from_registry(ephemeral_db):
    session = ephemeral_db
    svc = UniverseService(session=session)
    
    # Import non-existent world
    res = svc.import_from_registry("non-existent")
    assert res is None
    
    # Import existing world from registry
    res = svc.import_from_registry("world1")
    assert res is not None
    assert res.name == "World 1"
    assert res.slug == "world1"
    
    # Import world with parent
    res = svc.import_from_registry("world2")
    assert res is not None
    assert res.name == "World 2"
    assert res.parent_id is not None

def test_import_all_from_registry(ephemeral_db):
    session = ephemeral_db
    svc = UniverseService(session=session)
    
    imported, skipped = svc.import_all_from_registry()
    assert imported == 2
    assert skipped == 0
    
    # Import again to test skipping
    imported2, skipped2 = svc.import_all_from_registry()
    assert imported2 == 0
    assert skipped2 == 2

def test_delete_universe_comprehensive(ephemeral_db):
    session = ephemeral_db
    svc = UniverseService(session=session)
    
    u = Universe(name="DeleteMe", slug="deleteme")
    session.add(u)
    session.commit()
    session.refresh(u)
    
    # Create some child records
    from app.db.schema import Artifact, ArtifactRelation, Evidence, EvidenceChunk, WorldTier, Anomaly, UniverseRelation
    
    a1 = Artifact(name="A1", type="entity", universe_id=u.id)
    session.add(a1)
    session.commit()
    
    a2 = Artifact(name="A2", type="literal", universe_id=u.id)
    session.add(a2)
    session.commit()
    
    rel = ArtifactRelation(universe_id=u.id, from_artifact_id=a1.id, to_artifact_id=a2.id, relation_type="test")
    session.add(rel)
    
    ev = Evidence(universe_id=u.id, source_url="http://test.com")
    session.add(ev)
    session.commit()
    
    ec = EvidenceChunk(evidence_id=ev.id, content="chunk", chunk_index=0)
    session.add(ec)
    
    wt = WorldTier(universe_id=u.id, system_id=1, tier_number=1, justification="test")
    # Need a TierSystem
    ts = TierSystem(system_definition="test")
    session.add(ts)
    session.commit()
    wt.system_id = ts.id
    session.add(wt)
    
    an = Anomaly(universe_id=u.id, description="test anomaly")
    session.add(an)
    
    u_rel = UniverseRelation(from_universe_id=u.id, to_universe_id=u.id, relation_type="SELF")
    session.add(u_rel)
    
    session.commit()
    
    # Delete
    svc.delete_universe(u.id)
    
    # Verify
    assert session.get(Universe, u.id) is None
    assert session.exec(select(Artifact).where(Artifact.universe_id == u.id)).all() == []
    assert session.exec(select(ArtifactRelation).where(ArtifactRelation.universe_id == u.id)).all() == []
    assert session.exec(select(Evidence).where(Evidence.universe_id == u.id)).all() == []
    assert session.exec(select(EvidenceChunk).where(EvidenceChunk.evidence_id == ev.id)).all() == []
    assert session.exec(select(WorldTier).where(WorldTier.universe_id == u.id)).all() == []
    assert session.exec(select(Anomaly).where(Anomaly.universe_id == u.id)).all() == []
    assert session.exec(select(UniverseRelation).where((UniverseRelation.from_universe_id == u.id) | (UniverseRelation.to_universe_id == u.id))).all() == []

def test_merge_worlds_comprehensive(ephemeral_db):
    session = ephemeral_db
    svc = UniverseService(session=session)
    
    u_keep = Universe(name="Keep", slug="keep")
    u_merge = Universe(name="Merge", slug="merge")
    session.add_all([u_keep, u_merge])
    session.commit()
    session.refresh(u_keep)
    session.refresh(u_merge)
    
    # 1. Artifacts: Merge entities by name
    from app.db.schema import Artifact, ArtifactRelation, ArtifactVersion, WorldTier, Anomaly, UniverseRelation, TierSystem
    e_keep = Artifact(name="CommonEntity", type="entity", universe_id=u_keep.id, evidence_refs='["ref1"]')
    e_merge = Artifact(name="CommonEntity", type="entity", universe_id=u_merge.id, evidence_refs='["ref2"]')
    e_unique = Artifact(name="UniqueEntity", type="entity", universe_id=u_merge.id)
    session.add_all([e_keep, e_merge, e_unique])
    session.commit()
    
    # 2. Artifact Versions
    av_keep = ArtifactVersion(artifact_id=e_keep.id, version=1, payload_json='{"v": 1}', evidence_refs='["ref1"]')
    av_merge = ArtifactVersion(artifact_id=e_merge.id, version=1, payload_json='{"v": 1_merge}', evidence_refs='["ref2"]')
    session.add_all([av_keep, av_merge])
    session.commit()
    
    # 3. Relations
    rel_merge = ArtifactRelation(universe_id=u_merge.id, from_artifact_id=e_merge.id, to_artifact_id=e_unique.id, relation_type="rel")
    session.add(rel_merge)
    session.commit()
    
    # 4. Other child records
    ts = TierSystem(system_definition="sys")
    session.add(ts)
    session.commit()
    
    wt = WorldTier(universe_id=u_merge.id, system_id=ts.id, tier_number=1, justification="j")
    an = Anomaly(universe_id=u_merge.id, description="anom")
    u_rel = UniverseRelation(from_universe_id=u_merge.id, to_universe_id=u_keep.id, relation_type="LINK")
    session.add_all([wt, an, u_rel])
    session.commit()
    
    # Execute Merge
    svc.merge_worlds(u_keep.id, u_merge.id)
    
    # Verify
    assert session.get(Universe, u_merge.id) is None
    
    # Entity merged? Evidence union?
    merged_entity = session.exec(select(Artifact).where(Artifact.name == "CommonEntity", Artifact.universe_id == u_keep.id)).first()
    assert merged_entity is not None
    assert "ref1" in merged_entity.evidence_refs
    assert "ref2" in merged_entity.evidence_refs
    
    # Version shifted?
    versions = session.exec(select(ArtifactVersion).where(ArtifactVersion.artifact_id == merged_entity.id).order_by(ArtifactVersion.version)).all()
    assert len(versions) == 2
    assert versions[0].version == 1
    assert versions[1].version == 2
    
    # Unique entity moved?
    assert session.exec(select(Artifact).where(Artifact.name == "UniqueEntity", Artifact.universe_id == u_keep.id)).first() is not None
    
    # Relation moved?
    assert session.exec(select(ArtifactRelation).where(ArtifactRelation.universe_id == u_keep.id)).first() is not None
    
    # Other records moved?
    assert session.exec(select(WorldTier).where(WorldTier.universe_id == u_keep.id)).first() is not None
    assert session.exec(select(Anomaly).where(Anomaly.universe_id == u_keep.id)).first() is not None
    assert session.exec(select(UniverseRelation).where(UniverseRelation.from_universe_id == u_keep.id, UniverseRelation.to_universe_id == u_keep.id)).first() is not None
