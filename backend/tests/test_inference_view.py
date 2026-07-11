import pytest

from app.db.schema import InferenceRule


class TestInferencePage:
    ENDPOINT = "/inference"

    def test_inference_page_returns_html(self, api_client):
        r = api_client.get(self.ENDPOINT)
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_materialize(self, api_client):
        r = api_client.post(f"{self.ENDPOINT}/materialize")
        assert r.status_code == 200
        assert "Successfully materialized" in r.text


class TestInferenceRules:
    ENDPOINT = "/inference/rules"

    @pytest.fixture
    def seeded_rule(self, clean_db):
        session = clean_db
        rule = InferenceRule(
            predicate_1="A", predicate_2="B",
            implied_predicate="C", status="PROPOSED"
        )
        session.add(rule)
        session.commit()
        session.refresh(rule)
        return rule

    def test_approve_nonexistent_rule(self, api_client):
        r = api_client.post(f"{self.ENDPOINT}/99999/approve")
        assert r.status_code == 404

    def test_approve_existing_rule(self, api_client, seeded_rule):
        r = api_client.post(f"{self.ENDPOINT}/{seeded_rule.id}/approve")
        assert r.status_code == 200

    def test_reject_nonexistent_rule(self, api_client):
        r = api_client.post(f"{self.ENDPOINT}/99999/reject")
        assert r.status_code == 404

    def test_reject_existing_rule(self, api_client, seeded_rule):
        r = api_client.post(f"{self.ENDPOINT}/{seeded_rule.id}/reject")
        assert r.status_code == 200
