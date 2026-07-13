import pytest
from sqlmodel import Session
from app.db.schema import Artifact, ArtifactRelation, Universe
from app.repositories.artifact import ArtifactRepository

class TestArtifactRepository:
    def test_get_by_universe(self, clean_db):
        repo = ArtifactRepository()
        u = Universe(name="TestUni")
        clean_db.add(u)
        clean_db.commit()
        clean_db.refresh(u)

        a1 = Artifact(name="A1", type="entity", universe_id=u.id)
        a2 = Artifact(name="A2", type="entity", universe_id=u.id)
        a3 = Artifact(name="A3", type="entity", universe_id=999) # Different universe
        clean_db.add_all([a1, a2, a3])
        clean_db.commit()

        results = repo.get_by_universe(clean_db, u.id)
        assert len(results) == 2
        assert any(a.name == "A1" for a in results)
        assert any(a.name == "A2" for a in results)

    def test_search_artifacts(self, clean_db):
        repo = ArtifactRepository()
        u = Universe(name="SearchUni")
        clean_db.add(u)
        clean_db.commit()
        clean_db.refresh(u)

        a1 = Artifact(name="Alpha", description="desc alpha", type="entity", universe_id=u.id)
        a2 = Artifact(name="Beta", description="desc beta", type="entity", universe_id=u.id)
        a3 = Artifact(name="Gamma", description="desc gamma", type="entity", universe_id=u.id)
        clean_db.add_all([a1, a2, a3])
        clean_db.commit()

        # Search by name
        results = repo.search_artifacts(clean_db, u.id, "Alpha")
        assert len(results) == 1
        assert results[0].name == "Alpha"

        # Search by description
        results = repo.search_artifacts(clean_db, u.id, "beta")
        assert len(results) == 1
        assert results[0].name == "Beta"

        # Search non-existent
        results = repo.search_artifacts(clean_db, u.id, "Zeta")
        assert len(results) == 0

    def test_get_artifact_with_details(self, clean_db):
        repo = ArtifactRepository()
        u = Universe(name="DetailUni")
        clean_db.add(u)
        clean_db.commit()
        clean_db.refresh(u)

        a1 = Artifact(name="A1", description="desc 1", type="entity", universe_id=u.id)
        a2 = Artifact(name="A2", description="desc 2", type="entity", universe_id=u.id)
        clean_db.add_all([a1, a2])
        clean_db.commit()
        clean_db.refresh(a1)
        clean_db.refresh(a2)

        rel = ArtifactRelation(
            universe_id=u.id,
            from_artifact_id=a1.id,
            to_artifact_id=a2.id,
            relation_type="RELATED"
        )
        clean_db.add(rel)
        clean_db.commit()

        detailed_a1 = repo.get_artifact_with_details(clean_db, a1.id)
        assert detailed_a1 is not None
        assert detailed_a1.name == "A1"
        
        # Check relations
        # Note: relations_from and relations_to are defined in schema.py
        assert len(detailed_a1.relations_from) == 1
        assert detailed_a1.relations_from[0].to_artifact_id == a2.id
        assert len(detailed_a1.relations_to) == 0 # a1 is the 'from' artifact
        
        # Check a2
        detailed_a2 = repo.get_artifact_with_details(clean_db, a2.id)
        assert detailed_a2 is not None
        assert len(detailed_a2.relations_to) == 1
        assert detailed_a2.relations_to[0].from_artifact_id == a1.id
