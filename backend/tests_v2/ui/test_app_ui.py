from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.v2 import AppConfig, create_app
from app.v2.initialize import initialize
from app.v2.models import (
    AuditDecisionRecord,
    CanonNode,
    CanonNodeRevision,
    ClaimConflict,
    CoverageRecord,
    EvidenceFragment,
    MaterialProposalFieldRecord,
    MaterialProposalRecord,
    NodeEvidence,
    OutboxEvent,
    PromotionDecision,
    Provider,
    ResearchGapRecord,
    ResearchWorkspace,
    Run,
    RunTarget,
    Source,
    SourceRevision,
    WorkflowSummary,
)
from app.v2.runtime import V2Runtime


@pytest.fixture
def ui_runtime(isolated_paths: dict[str, Path], tmp_path: Path) -> V2Runtime:
    seed = tmp_path / "worlds.json"
    seed.write_text(
        json.dumps(
            [
                {
                    "id": "world-alpha",
                    "name": "Alpha <script>alert(1)</script>",
                    "franchise": "Test Franchise",
                    "category": "Science Fiction",
                    "continuity": "Prime",
                    "era": None,
                    "parent": None,
                    "aliases": [],
                    "tags": ["space"],
                },
                {
                    "id": "world-beta",
                    "name": "Beta",
                    "franchise": "Test Franchise",
                    "category": "Fantasy",
                    "continuity": "Main",
                    "era": None,
                    "parent": None,
                    "aliases": [],
                    "tags": [],
                },
            ]
        ),
        encoding="utf-8",
    )
    config = AppConfig(
        database_path=isolated_paths["database"],
        blob_path=isolated_paths["blobs"],
        credentials_path=isolated_paths["credentials"],
        seed_path=seed,
    ).runtime_config()
    initialize(config)
    return V2Runtime.build(config, adapters={})


@pytest.fixture
def client(ui_runtime: V2Runtime) -> TestClient:
    app = create_app(runtime=ui_runtime, start_worker=False)
    with TestClient(app) as value:
        yield value


def test_shell_nav_static_and_mobile_basics(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert '<meta name="viewport"' in response.text
    assert 'id="sidebar"' in response.text
    assert 'id="mobile-menu-toggle"' in response.text
    for path in (
        "/research/",
        "/knowledge/",
        "/validation/",
        "/flow/",
        "/logs/",
        "/settings/",
    ):
        assert f'href="{path}"' in response.text
    stylesheet = client.get("/static/css/main.css")
    assert stylesheet.status_code == 200
    assert "@media (max-width: 767px)" in stylesheet.text
    assert "#sidebar.open" in stylesheet.text


def test_injected_runtime_does_not_start_worker(
    ui_runtime: V2Runtime, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = False

    def fail_start() -> None:
        nonlocal started
        started = True

    monkeypatch.setattr(ui_runtime.worker, "start", fail_start)
    with TestClient(create_app(runtime=ui_runtime, start_worker=False)) as value:
        assert value.get("/").status_code == 200
    assert started is False


def test_research_world_search_uses_string_ids_and_escapes_html(
    client: TestClient,
) -> None:
    page = client.get("/research/")
    assert page.status_code == 200
    assert 'hx-get="/research/worlds"' in page.text
    assert 'hx-target="#world-results"' in page.text
    assert 'hx-trigger="keyup changed delay:300ms, search"' in page.text
    assert 'hx-swap="innerHTML"' in page.text
    assert 'value="identity_scope" checked' in page.text
    assert 'value="counters_limits" checked' in page.text
    response = client.get(
        "/research/worlds", params={"q": "Alpha"}, headers={"HX-Request": "true"}
    )
    assert response.status_code == 200
    assert 'value="world-alpha"' in response.text
    assert "&lt;script&gt;" in response.text
    assert "<script>alert(1)</script>" not in response.text


def test_multiselect_run_create_is_202_html_and_idempotent(client: TestClient) -> None:
    form = {
        "world_ids": ["world-alpha", "world-beta"],
        "objective": "Map canon",
        "continuity": "Prime",
        "domains": ["mechanisms", "constraints"],
        "idempotency_key": "ui-create-1",
    }
    created = client.post("/research/runs", data=form, headers={"HX-Request": "true"})
    assert created.status_code == 202
    assert created.headers["content-type"].startswith("text/html")
    assert created.headers["HX-Retarget"] == "#run-queue"
    assert "world-alpha" in created.text
    assert "world-beta" in created.text
    assert "PENDING" in created.text
    repeated = client.post("/research/runs", data=form, headers={"HX-Request": "true"})
    assert repeated.status_code == 202
    assert repeated.text == created.text


def test_run_queue_polling_cancel_and_terminal_poll_stop(client: TestClient) -> None:
    created = client.post(
        "/research/runs",
        data={
            "world_ids": "world-alpha",
            "objective": "Map canon",
            "continuity": "Prime",
            "domains": "mechanisms",
            "idempotency_key": "cancel-me",
        },
    )
    run_id = created.headers["X-Run-ID"]
    detail = client.get(f"/research/runs/{run_id}")
    assert 'hx-trigger="every 2s"' in detail.text
    cancelled = client.post(
        f"/research/runs/{run_id}/cancel", headers={"HX-Request": "true"}
    )
    assert cancelled.status_code == 200
    assert "CANCELLED" in cancelled.text
    assert 'hx-trigger="every 2s"' not in cancelled.text
    assert client.post(f"/research/runs/{run_id}/retry").status_code == 409


def test_deprecated_routes_and_theory_deferred(client: TestClient) -> None:
    for path in ("/worlds", "/worlds/", "/research/choose-world"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code in {307, 308}
        assert response.headers["location"] == "/research/"
    theory = client.get("/theory/")
    assert theory.status_code == 200
    assert "Deferred" in theory.text
    assert "non-canon" in theory.text.lower()
    assert "hx-post" not in theory.text


@pytest.fixture
def projected_client(ui_runtime: V2Runtime) -> TestClient:
    now = datetime.now(timezone.utc)
    with Session(ui_runtime.engine) as session, session.begin():
        run = Run(
            id="run-text-001",
            kind="RESEARCH",
            status="SUCCEEDED",
            idempotency_key="projected-run",
            payload_hash="a" * 64,
            objective="Projected run <script>alert(2)</script>",
            scope_json={"continuity": "Prime"},
            outcome="COMPLETE",
        )
        session.add(run)
        session.flush()
        target = RunTarget(
            id="target-projected",
            run_id=run.id,
            world_id="world-alpha",
            objective=run.objective,
            scope_json={"continuity": "Prime"},
            outcome="COMPLETE",
        )
        session.add(target)
        session.flush()
        workspace = ResearchWorkspace(
            id="workspace-1",
            run_id=run.id,
            target_id=target.id,
            world_id="world-alpha",
            continuity="Prime",
            brief_json={},
            status="COMPLETE",
        )
        session.add(workspace)
        source = Source(
            id="source-1",
            canonical_url="https://example.test/canon",
            source_class="PRIMARY",
            publisher="Example",
        )
        session.add(source)
        session.flush()
        source_revision = SourceRevision(
            id="source-revision-1",
            source_id=source.id,
            content_hash="b" * 64,
            retrieved_at=now,
            status_code=200,
            content_type="text/html",
        )
        session.add(source_revision)
        session.flush()
        fragment = EvidenceFragment(
            id="fragment-1",
            source_revision_id=source_revision.id,
            locator="p:1",
            exact_excerpt="Exact canon excerpt",
            content_hash="c" * 64,
            domain="mechanisms",
            world_id="world-alpha",
            support_role="SUPPORTS",
        )
        session.add(fragment)
        node = CanonNode(
            id="node-1", world_id="world-alpha", kind="MECHANISM", modality="MAGICAL"
        )
        session.add(node)
        session.flush()
        old_revision = CanonNodeRevision(
            id="node-revision-old",
            node_id=node.id,
            revision_number=1,
            fields_json={"effect": "Old rejected text"},
            scope_json={"continuity": "Prime"},
        )
        accepted_revision = CanonNodeRevision(
            id="node-revision-accepted",
            node_id=node.id,
            revision_number=2,
            fields_json={"effect": "Accepted effect"},
            scope_json={"continuity": "Prime"},
        )
        session.add_all([old_revision, accepted_revision])
        session.flush()
        session.add(
            NodeEvidence(
                node_revision_id=accepted_revision.id,
                evidence_fragment_id=fragment.id,
                field_name="effect",
            )
        )
        session.add(
            CoverageRecord(
                id="coverage-1",
                workspace_id=workspace.id,
                world_id="world-alpha",
                domain="mechanisms",
                continuity="Prime",
                status="COVERED",
                indicators_json=["effect"],
            )
        )
        session.add(
            WorkflowSummary(
                id="summary-1",
                run_id=run.id,
                target_id=target.id,
                summary_json={"overview": "Canonical summary"},
            )
        )
        session.add(
            ResearchGapRecord(
                id="gap-1",
                workspace_id=workspace.id,
                gap_json={"domain": "limits", "question": "What is the limit?"},
            )
        )
        proposal = MaterialProposalRecord(
            id="proposal-1",
            workspace_id=workspace.id,
            kind="MECHANISM",
            scope_json={"world_id": "world-alpha"},
            fields_json={"effect": "Candidate effect"},
        )
        session.add(proposal)
        session.flush()
        field = MaterialProposalFieldRecord(
            id="proposal-field-1",
            proposal_id=proposal.id,
            name="effect",
            value_json="Candidate effect",
        )
        session.add(field)
        session.flush()
        session.add(
            ClaimConflict(
                id="conflict-1",
                proposal_field_id=field.id,
                workspace_id=workspace.id,
                status="OPEN",
            )
        )
        session.add(
            AuditDecisionRecord(
                id="audit-1",
                proposal_id=proposal.id,
                field_name="effect",
                verdict="NEEDS_EVIDENCE",
                reason_code="MISSING_PRIMARY",
                assertion_type="FIELD",
                assertion_id=field.id,
                evidence_fragment_ids_json=[fragment.id],
                policy_version="audit.v1",
            )
        )
        session.add(
            PromotionDecision(
                id="promotion-1",
                proposal_id=proposal.id,
                decision="REJECTED",
            )
        )
        session.add(
            OutboxEvent(
                id="event-z",
                run_id=run.id,
                event_type="RUN_FINISHED",
                payload_json={"message": "<script>alert(3)</script>"},
                effect_key="projected-finished",
                created_at=now,
            )
        )
        session.add(Provider(id="provider-string", kind="OPENAI", active=True))
    with TestClient(create_app(runtime=ui_runtime, start_worker=False)) as value:
        yield value


def test_knowledge_tabs_accepted_canon_gaps_conflicts(
    projected_client: TestClient,
) -> None:
    page = projected_client.get("/knowledge/", params={"world_id": "world-alpha"})
    assert page.status_code == 200
    for tab in ("Overview", "Canon", "Evidence", "Gaps"):
        assert tab in page.text
    assert ">Theory</button>" not in page.text
    canon = projected_client.get("/knowledge/world-alpha/canon")
    assert "Accepted effect" in canon.text
    assert "Old rejected text" not in canon.text
    assert "/provenance/node-1" in canon.text
    gaps = projected_client.get("/knowledge/world-alpha/gaps")
    assert "What is the limit?" in gaps.text
    assert "conflict-1" in gaps.text


def test_complete_provenance_chain(projected_client: TestClient) -> None:
    response = projected_client.get("/provenance/node-1")
    assert response.status_code == 200
    for value in (
        "node-revision-accepted",
        "effect",
        "Exact canon excerpt",
        "source-revision-1",
        "https://example.test/canon",
    ):
        assert value in response.text


def test_validation_is_durable_audit_queue_not_fake_actions(
    projected_client: TestClient,
) -> None:
    response = projected_client.get("/validation/")
    assert response.status_code == 200
    for value in ("NEEDS_EVIDENCE", "MISSING_PRIMARY", "REJECTED", "conflict-1"):
        assert value in response.text
    assert "Approve" not in response.text
    assert "Delete" not in response.text
    first = projected_client.post("/validation/audits/audit-1/follow-up")
    assert first.status_code == 202
    assert "PENDING" in first.text
    second = projected_client.post("/validation/audits/audit-1/follow-up")
    assert second.status_code == 202
    assert second.headers["X-Run-ID"] == first.headers["X-Run-ID"]


def test_flow_is_ordered_and_uses_text_run_ids(projected_client: TestClient) -> None:
    index = projected_client.get("/flow/")
    assert "run-text-001" in index.text
    detail = projected_client.get("/flow/run-text-001")
    assert detail.status_code == 200
    assert "RUN_FINISHED" in detail.text
    assert "run-text-001" in detail.text


def test_logs_filters_and_escapes_durable_events(projected_client: TestClient) -> None:
    response = projected_client.get(
        "/logs/", params={"run_id": "run-text-001", "event_type": "RUN_FINISHED"}
    )
    assert response.status_code == 200
    for field in ("run_id", "world_id", "status", "event_type"):
        assert f'name="{field}"' in response.text
    assert "&lt;script&gt;alert(3)&lt;/script&gt;" in response.text
    assert "<script>alert(3)</script>" not in response.text
    assert "clear-logs" not in response.text


def test_logs_use_stable_keyset_pagination_and_preserve_filters(
    projected_client: TestClient,
) -> None:
    engine = projected_client.app.state.runtime.engine
    created = datetime(2026, 7, 24, tzinfo=timezone.utc)
    with Session(engine) as session, session.begin():
        session.add_all(
            OutboxEvent(
                id=f"event-page-{index:03d}",
                run_id="run-text-001",
                event_type="PAGE_TEST",
                payload_json={"index": index},
                effect_key=f"page-test:{index}",
                created_at=created + timedelta(seconds=index),
            )
            for index in range(105)
        )

    first = projected_client.get(
        "/logs/", params={"run_id": "run-text-001", "event_type": "PAGE_TEST"}
    )
    href_match = re.search(r'href="([^"]+)">Older events</a>', first.text)
    assert href_match is not None
    href = unescape(href_match.group(1))
    assert "run_id=run-text-001" in href
    assert "event_type=PAGE_TEST" in href
    first_ids = set(re.findall(r"<code>(event-page-\d+)</code>", first.text))

    second = projected_client.get(href)
    second_ids = set(re.findall(r"<code>(event-page-\d+)</code>", second.text))
    assert len(first_ids) == 100
    assert len(second_ids) == 5
    assert first_ids.isdisjoint(second_ids)


def test_settings_string_ids_masked_credentials_route_order_and_health(
    projected_client: TestClient,
) -> None:
    page = projected_client.get("/settings/")
    assert page.status_code == 200
    for tab in ("General", "Providers", "Models", "Routes", "Health"):
        assert tab in page.text
    general = projected_client.get("/settings/tab/general")
    assert "omniverse.db" in general.text
    assert "Worker" in general.text
    providers = projected_client.get("/settings/tab/providers")
    assert "provider-string" in providers.text
    created = projected_client.post(
        "/settings/providers/provider-string/credentials",
        data={"label": "primary", "secret": "super-secret", "weight": "1"},
    )
    assert created.status_code == 201
    assert "super-secret" not in created.text
    assert "opaque_ref" not in created.text
    assert "********" in created.text
    credential_id = created.headers["X-Credential-ID"]
    assert (
        projected_client.post(
            f"/settings/health/credentials/{credential_id}/reset"
        ).status_code
        == 200
    )
    assert (
        projected_client.delete(
            f"/settings/providers/provider-string/credentials/{credential_id}"
        ).status_code
        == 200
    )


def test_settings_updates_provider_models_and_ordered_routes(
    projected_client: TestClient,
) -> None:
    updated = projected_client.post(
        "/settings/providers/provider-string",
        data={"base_url": "https://models.example/v1", "active": "true"},
    )
    assert updated.status_code == 200
    assert "https://models.example/v1" in updated.text

    for model_id, model_name in (("model-a", "Alpha"), ("model-b", "Beta")):
        model = projected_client.post(
            f"/settings/providers/provider-string/models/{model_id}",
            data={
                "model_name": model_name,
                "context_window": "32000",
                "output_limit": "2000",
                "supports_tools": "true",
                "supports_structured": "true",
                "supports_text": "true",
                "active": "true",
            },
        )
        assert model.status_code == 200
        assert model_id in model.text

    route = projected_client.post(
        "/settings/routes/research.plan",
        data={"model_ids": ["model-b", "model-a"], "weights": ["2", "1"]},
    )
    assert route.status_code == 200
    assert route.text.index("model-b") < route.text.index("model-a")
    assert ">0<" in route.text
    assert ">1<" in route.text
