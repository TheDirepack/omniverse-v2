from app.db.schema import Artifact, ArtifactRelation, Evidence, EvidenceChunk, Universe


class TestFlowPage:
    ENDPOINT = "/flow"

    def test_flow_page_returns_html(self, api_client):
        r = api_client.get(self.ENDPOINT)
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")


class TestTraceClaim:
    ENDPOINT = "/flow"

    def test_trace_nonexistent_claim(self, api_client):
        r = api_client.get(f"{self.ENDPOINT}/99999")
        assert r.status_code == 404

    def test_trace_claim_with_trace_query(self, api_client, clean_db):
        session = clean_db
        u = Universe(name="FlowTest")
        session.add(u)
        session.commit()
        session.refresh(u)

        e = Artifact(name="FlowEntity", type="entity", universe_id=u.id)
        session.add(e)
        session.commit()
        session.refresh(e)

        lit = Artifact(name="obj_val", type="literal", universe_id=u.id)
        session.add(lit)
        session.commit()
        session.refresh(lit)

        c = ArtifactRelation(
            universe_id=u.id, from_artifact_id=e.id,
            to_artifact_id=lit.id, relation_type="flow_pred"
        )
        session.add(c)
        session.commit()
        session.refresh(c)

        r = api_client.get(f"{self.ENDPOINT}/trace?claim_id={c.id}")
        assert r.status_code == 200

    def test_trace_claim_with_evidence_chunk(self, api_client, clean_db):
        session = clean_db
        u = Universe(name="EvidUni")
        session.add(u)
        session.commit()
        session.refresh(u)

        ev = Evidence(source_url="http://example.com", universe_id=u.id)
        session.add(ev)
        session.commit()
        session.refresh(ev)

        chunk = EvidenceChunk(evidence_id=ev.id, content="test", chunk_index=0)
        session.add(chunk)
        session.commit()
        session.refresh(chunk)

        e = Artifact(name="EvidEnt", type="entity", universe_id=u.id)
        session.add(e)
        session.commit()
        session.refresh(e)

        lit = Artifact(name="val", type="literal", universe_id=u.id)
        session.add(lit)
        session.commit()
        session.refresh(lit)

        c = ArtifactRelation(
            universe_id=u.id, from_artifact_id=e.id,
            to_artifact_id=lit.id, relation_type="test_pred"
        )
        session.add(c)
        session.commit()
        session.refresh(c)

        r = api_client.get(f"{self.ENDPOINT}/{c.id}")
        assert r.status_code == 200

    def test_trace_claim_with_object_entity(self, api_client, clean_db):
        session = clean_db
        u = Universe(name="ObjUni")
        session.add(u)
        session.commit()
        session.refresh(u)

        subj = Artifact(name="Subject", type="entity", universe_id=u.id)
        obj = Artifact(name="Object", type="entity", universe_id=u.id)
        session.add_all([subj, obj])
        session.commit()
        session.refresh(subj)
        session.refresh(obj)

        c = ArtifactRelation(
            universe_id=u.id, from_artifact_id=subj.id,
            to_artifact_id=obj.id, relation_type="RELATES_TO"
        )
        session.add(c)
        session.commit()
        session.refresh(c)

        r = api_client.get(f"{self.ENDPOINT}/{c.id}")
        assert r.status_code == 200
