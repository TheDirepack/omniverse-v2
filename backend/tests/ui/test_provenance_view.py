from app.db.schema import Artifact, ArtifactRelation, Universe


class TestProvenanceForClaim:
    ENDPOINT = "/provenance/claim"

    def test_nonexistent_claim(self, api_client):
        r = api_client.get(f"{self.ENDPOINT}/99999")
        assert r.status_code == 404

    def test_existing_claim(self, api_client, clean_db):
        session = clean_db
        u = Universe(name="ProvTest")
        session.add(u)
        session.commit()
        session.refresh(u)
        e = Artifact(name="ProvEnt", type="entity", universe_id=u.id)
        session.add(e)
        session.commit()
        session.refresh(e)
        lit = Artifact(name="val", type="literal", universe_id=u.id)
        session.add(lit)
        session.commit()
        session.refresh(lit)
        c = ArtifactRelation(
            universe_id=u.id,
            from_artifact_id=e.id,
            to_artifact_id=lit.id,
            relation_type="test",
        )
        session.add(c)
        session.commit()
        session.refresh(c)

        r = api_client.get(f"{self.ENDPOINT}/{c.id}")
        assert r.status_code == 200


class TestProvenanceForArtifact:
    ENDPOINT = "/provenance/artifact"

    def test_nonexistent_artifact(self, api_client):
        r = api_client.get(f"{self.ENDPOINT}/99999")
        assert r.status_code == 404
