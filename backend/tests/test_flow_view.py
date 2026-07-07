import pytest
from app.db.schema import Claim, Entity, Predicate, Evidence, EvidenceChunk, Universe


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

        e = Entity(name="FlowEntity", entity_type="T", universe_id=u.id)
        session.add(e)
        session.commit()
        session.refresh(e)

        p = Predicate(canonical_name="flow_pred")
        session.add(p)
        session.commit()
        session.refresh(p)

        c = Claim(
            subject_id=e.id, predicate="flow_pred",
            object_literal="obj_val", predicate_id=p.id
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

        e = Entity(name="EvidEnt", entity_type="T", universe_id=u.id)
        session.add(e)
        session.commit()
        session.refresh(e)

        c = Claim(
            subject_id=e.id, predicate="test_pred",
            object_literal="val", evidence_chunk_id=chunk.id
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

        subj = Entity(name="Subject", entity_type="T", universe_id=u.id)
        obj = Entity(name="Object", entity_type="T", universe_id=u.id)
        session.add_all([subj, obj])
        session.commit()
        session.refresh(subj)
        session.refresh(obj)

        c = Claim(
            subject_id=subj.id, predicate="RELATES_TO",
            object_entity_id=obj.id, object_literal=None
        )
        session.add(c)
        session.commit()
        session.refresh(c)

        r = api_client.get(f"{self.ENDPOINT}/{c.id}")
        assert r.status_code == 200
