from unittest.mock import AsyncMock, patch

from app.db.schema import InferenceRule


class TestDepthEndpoints:
    def test_get_depth_default(self, client):
        client.put("/api/inference/depth", json={"max_composition_depth": 2})
        r = client.get("/api/inference/depth")
        assert r.status_code == 200
        assert r.json()["max_composition_depth"] == 2

    def test_set_depth(self, client):
        r = client.put("/api/inference/depth", json={"max_composition_depth": 4})
        assert r.status_code == 200
        assert r.json()["max_composition_depth"] == 4
        r2 = client.get("/api/inference/depth")
        assert r2.json()["max_composition_depth"] == 4

    def test_set_depth_rejects_zero(self, client):
        r = client.put("/api/inference/depth", json={"max_composition_depth": 0})
        assert r.status_code == 422  # pydantic ge=1 validation

    def test_set_depth_rejects_negative(self, client):
        r = client.put("/api/inference/depth", json={"max_composition_depth": -3})
        assert r.status_code == 422

    def test_set_depth_rejects_above_max(self, client):
        r = client.put("/api/inference/depth", json={"max_composition_depth": 11})
        assert r.status_code == 422  # pydantic le=10 validation

    def test_set_depth_rejects_non_integer(self, client):
        r = client.put("/api/inference/depth", json={"max_composition_depth": "three"})
        assert r.status_code == 422


class TestRuleProposalTrigger:
    def test_propose_endpoint_returns_run_id(self, client):
        with patch(
            "app.api.routers.inference.run_rule_proposal_in_background", new=AsyncMock()
        ) as mock_task:
            r = client.post("/api/inference/rules/propose")
            assert r.status_code == 200
            data = r.json()
            assert data["status"] == "started"
            assert "run_id" in data
            mock_task.assert_called_once()


class TestRuleListingAndApproval:
    def test_list_rules_empty(self, client):
        r = client.get("/api/inference/rules")
        assert r.status_code == 200
        data = r.json()
        assert data["proposed"] == []
        assert data["approved"] == []

    def test_list_rules_by_status(self, ephemeral_db, client):
        rule = InferenceRule(
            predicate_1="USES",
            predicate_2="GENERATES",
            implied_predicate="PRODUCES",
            status="CRITIQUED",
        )
        ephemeral_db.add(rule)
        ephemeral_db.commit()
        r = client.get("/api/inference/rules?status=CRITIQUED")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["predicate_1"] == "USES"

    def test_approve_rule_endpoint(self, ephemeral_db, client):
        rule = InferenceRule(
            predicate_1="USES",
            predicate_2="GENERATES",
            implied_predicate="PRODUCES",
            status="CRITIQUED",
        )
        ephemeral_db.add(rule)
        ephemeral_db.commit()
        ephemeral_db.refresh(rule)

        r = client.post(f"/api/inference/rules/{rule.id}/approve")
        assert r.status_code == 200
        assert r.json()["human_approved"] is True
        assert r.json()["status"] == "APPROVED"

    def test_approve_nonexistent_rule_404(self, client):
        r = client.post("/api/inference/rules/99999/approve")
        assert r.status_code == 404

    def test_list_rules_unknown_status_returns_empty(self, ephemeral_db, client):
        rule = InferenceRule(
            predicate_1="USES",
            predicate_2="GENERATES",
            implied_predicate="PRODUCES",
            status="CRITIQUED",
        )
        ephemeral_db.add(rule)
        ephemeral_db.commit()
        r = client.get("/api/inference/rules?status=NOT_A_REAL_STATUS")
        assert r.status_code == 200
        assert r.json() == []

    def test_approve_then_reject_overwrites_state(self, ephemeral_db, client):
        """Approving then rejecting the same rule should leave it in the
        rejected state, not some inconsistent hybrid."""
        rule = InferenceRule(
            predicate_1="USES",
            predicate_2="GENERATES",
            implied_predicate="PRODUCES",
            status="CRITIQUED",
        )
        ephemeral_db.add(rule)
        ephemeral_db.commit()
        ephemeral_db.refresh(rule)

        client.post(f"/api/inference/rules/{rule.id}/approve")
        r = client.post(f"/api/inference/rules/{rule.id}/reject")
        assert r.status_code == 200
        assert r.json()["status"] == "REJECTED"
        assert r.json()["human_approved"] is False

    def test_reject_rule_endpoint(self, ephemeral_db, client):
        rule = InferenceRule(
            predicate_1="USES",
            predicate_2="GENERATES",
            implied_predicate="PRODUCES",
            status="CRITIQUED",
        )
        ephemeral_db.add(rule)
        ephemeral_db.commit()
        ephemeral_db.refresh(rule)

        r = client.post(f"/api/inference/rules/{rule.id}/reject")
        assert r.status_code == 200
        assert r.json()["status"] == "REJECTED"
        assert r.json()["human_approved"] is False


class TestMaterializationEndpoint:
    def test_materialize_with_no_rules_creates_nothing(self, client):
        r = client.post("/api/inference/materialize")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "completed"
        assert data["created_count"] == 0

    def test_materialize_with_approved_rule(self, ephemeral_db, client):
        from app.db.schema import Claim, Entity, Universe

        u = Universe(name="TestUniverse", is_explored=True)
        ephemeral_db.add(u)
        ephemeral_db.commit()
        ephemeral_db.refresh(u)

        a = Entity(name="A", entity_type="X", universe_id=u.id)
        b = Entity(name="B", entity_type="X", universe_id=u.id)
        c = Entity(name="C", entity_type="X", universe_id=u.id)
        ephemeral_db.add_all([a, b, c])
        ephemeral_db.commit()
        for e in [a, b, c]:
            ephemeral_db.refresh(e)

        ephemeral_db.add_all(
            [
                Claim(subject_id=a.id, predicate="USES", object_entity_id=b.id),
                Claim(subject_id=b.id, predicate="GENERATES", object_entity_id=c.id),
            ]
        )
        ephemeral_db.commit()

        rule = InferenceRule(
            predicate_1="USES",
            predicate_2="GENERATES",
            implied_predicate="PRODUCES",
            status="APPROVED",
            human_approved=True,
        )
        ephemeral_db.add(rule)
        ephemeral_db.commit()

        r = client.post("/api/inference/materialize")
        assert r.status_code == 200
        assert r.json()["created_count"] == 1


class TestContradictionsEndpoint:
    def test_list_contradictions_empty(self, client):
        r = client.get("/api/inference/contradictions")
        assert r.status_code == 200
        assert r.json() == []
