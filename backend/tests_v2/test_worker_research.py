from __future__ import annotations

import asyncio
import json

import anyio
import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_evidence_workflow import FakeSearch, command, responses

from app.v2.bootstrap import import_world_seed
from app.v2.config import V2Config
from app.v2.db import bootstrap_schema
from app.v2.models import (
    CanonNode,
    CanonNodeRevision,
    EvidenceFragment,
    IntegrationEffect,
    ModelCall,
    ModelStepEffect,
    Provider,
    ProviderModel,
    Route,
    RouteCandidate,
    Source,
    SourceRevision,
    World,
)
from app.v2.runtime import V2Runtime


class OfflineResolver:
    async def resolve(self, host: str) -> tuple[str, ...]:
        assert host == "example.test"
        return ("93.184.216.34",)


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize(
    "transient_failure", [False, True], ids=["healthy", "manual-retry"]
)
async def test_runtime_worker_research_completes_offline(
    isolated_paths, tmp_path, monkeypatch, transient_failure
):
    seed = tmp_path / "worlds.json"
    seed.write_text("[]", encoding="utf-8")
    config = V2Config(
        database_path=isolated_paths["database"],
        blob_path=isolated_paths["blobs"],
        credentials_path=isolated_paths["credentials"],
        seed_path=seed,
        logging_root=tmp_path,
        browser_profile_path=tmp_path / "browser",
        browser_enabled=False,
        preprocessor_enabled=False,
        remote_model_lifecycle_enabled=False,
        worker_poll_seconds=0.01,
        http_timeout_seconds=2,
    )
    values = responses()
    tasks = dict(
        zip(
            (
                "PlannerOutput",
                "ExtractorOutput",
                "SynthesizerOutput",
                "AuditorOutput",
                "SummaryOutput",
            ),
            values,
            strict=True,
        )
    )
    model_calls = []
    source_calls = []
    excerpt = "The prototype fusion engine bends local spacetime."

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.host == "provider.test":
            assert request.method == "POST"
            assert request.url.path == "/v1/chat/completions"
            assert request.headers["authorization"] == "Bearer offline-dummy"
            payload = json.loads(request.content)
            assert payload["model"] == "offline-model"
            task = tasks[payload["response_format"]["json_schema"]["schema"]["title"]]
            model_calls.append(task)
            assert len(model_calls) <= 6
            if transient_failure and len(model_calls) == 1:
                return httpx.Response(
                    503,
                    headers={"Retry-After": "1"},
                    json={"error": {"message": "temporary offline fixture failure"}},
                )
            context = json.loads(payload["messages"][-1]["content"])
            value = values[task].pop(0)
            if task == "research.extract":
                for fragment in value["fragments"]:
                    fragment["source_revision_id"] = context["task"][
                        "source_revision_id"
                    ]
                    fragment["locator"] = next(
                        passage["locator"]
                        for passage in context["task"]["authoritative_passages"]
                        if fragment["exact_excerpt"] in passage["text"]
                    )
            if task in {"research.synthesize", "research.audit", "research.summary"}:
                # Bind canned local references to the evidence actually supplied.
                encoded = json.dumps(value)
                for local_id, text in (
                    ("fragment-support", excerpt),
                    ("fragment-qualifier", "prototype"),
                ):
                    actual = next(
                        item["fragment_id"]
                        for item in context["evidence"]
                        if item["exact_excerpt"] == text
                    )
                    encoded = encoded.replace(local_id, actual)
                value = json.loads(encoded)
            if task == "research.synthesize":
                value["proposals"][0]["scope"] = context["task"]["scope"]
            if task == "research.summary":
                fact = context["task"]["accepted_facts"][0]
                value["facts"][0].update(
                    {key: fact[key] for key in ("node_id", "node_revision_id")}
                )
            return httpx.Response(
                200,
                json={
                    "id": f"offline-response-{len(model_calls)}",
                    "model": "offline-model",
                    "choices": [
                        {
                            "message": {"content": json.dumps(value)},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 10},
                },
            )
        assert request.url.host == "example.test", str(request.url)
        assert request.method == "GET"
        source_calls.append(request.url.path)
        assert len(source_calls) <= 10
        if request.url.path == "/sitemap.xml":
            return httpx.Response(
                200,
                headers={"Content-Type": "application/xml"},
                text=(
                    "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"
                    "<url><loc>https://example.test/fusion</loc></url></urlset>"
                ),
            )
        assert request.url.path == "/fusion", str(request.url)
        return httpx.Response(200, headers={"Content-Type": "text/plain"}, text=excerpt)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as outbound:
        runtime = V2Runtime.build(
            config,
            http_client=outbound,
            search_provider=FakeSearch(),
            resolver=OfflineResolver(),
        )
        bootstrap_schema(runtime.engine)
        import_world_seed(runtime.engine, seed)
        with Session(runtime.engine) as session, session.begin():
            session.add(
                World(
                    id="world-1",
                    name="Example",
                    franchise="Example",
                    category="SF",
                    continuity="prime",
                )
            )
            session.add(
                Provider(id="offline", kind="OPENAI", base_url="https://provider.test")
            )
            session.add(Route(id="offline-route", task="DEFAULT", position=0))
            session.flush()
            session.add(
                ProviderModel(
                    id="offline-model",
                    provider_id="offline",
                    model_name="offline-model",
                    context_window=100_000,
                    output_limit=16_000,
                    supports_structured=True,
                )
            )
            session.flush()
            session.add(
                RouteCandidate(
                    id="offline-candidate",
                    route_id="offline-route",
                    model_id="offline-model",
                    position=0,
                )
            )
        runtime.credentials.add("offline", "Test only", "offline-dummy")
        # main constructs a default app on first import; reuse the isolated runtime.
        with monkeypatch.context() as importing:
            importing.setattr(V2Config, "from_env", classmethod(lambda cls: config))
            importing.setattr(
                V2Runtime, "build", classmethod(lambda cls, *args, **kwargs: runtime)
            )
            from app.v2.main import create_app

        app = create_app(runtime=runtime, start_worker=True)
        with anyio.fail_after(30):
            async with app.router.lifespan_context(app):
                worker_tasks = list(runtime.worker._tasks)
                await asyncio.sleep(0)
                worker_tasks.extend(runtime.worker._tasks)
                assert worker_tasks and all(not task.done() for task in worker_tasks)
                assert runtime.worker.workflow is runtime.workflow
                assert runtime.provider_router.adapters["offline"].client is outbound
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app), base_url="http://testserver"
                ) as client:
                    payload = command().model_dump(mode="json")
                    payload["max_attempts"] = 1
                    created = await client.post(
                        "/api/v2/research-runs",
                        headers={"Idempotency-Key": "worker-offline"},
                        json=payload,
                    )
                    assert created.status_code == 202, created.text
                    location = created.headers["Location"]
                    retried = False
                    for _ in range(300):
                        polled = await client.get(location)
                        assert polled.status_code == 200
                        result = polled.json()
                        if result["outcome"] == "COMPLETE":
                            break
                        if (
                            transient_failure
                            and not retried
                            and result["outcome"] == "PARTIAL"
                        ):
                            assert model_calls == ["research.plan"]
                            plan = next(
                                step
                                for step in result["steps"]
                                if step["kind"] == "PLAN"
                            )
                            assert plan["status"] == "FAILED"
                            assert plan["attempt_count"] == 1
                            assert "ProviderError" in plan["error"]
                            assert (
                                await client.get(
                                    "/api/v2/canon", params={"world_id": "world-1"}
                                )
                            ).json()["items"] == []
                            await asyncio.sleep(
                                1.1
                            )  # Honor the real router's cooldown.
                            retry = await client.post(f"{location}/retry")
                            assert retry.status_code == 200, retry.text
                            retried = True
                        elif result["status"] in {"FAILED", "SUCCEEDED", "CANCELLED"}:
                            pytest.fail(f"Unexpected terminal run: {result}")
                        await asyncio.sleep(0.02)
                    else:
                        pytest.fail(
                            f"Worker did not complete: {result}; calls={model_calls}"
                        )
                    assert result["status"] == "SUCCEEDED"
                    assert retried == transient_failure
                    assert all(
                        step["status"] == "SUCCEEDED" for step in result["steps"]
                    )
                    for step in result["steps"]:
                        failed_plan = transient_failure and step["kind"] == "PLAN"
                        assert step["attempt_count"] == (2 if failed_plan else 1)
                        assert [attempt["status"] for attempt in step["attempts"]] == (
                            ["FAILED", "SUCCEEDED"] if failed_plan else ["SUCCEEDED"]
                        )
                    canon = await client.get(
                        "/api/v2/canon", params={"world_id": "world-1"}
                    )
                    assert canon.status_code == 200
                    assert len(canon.json()["items"]) == 1
                    node = canon.json()["items"][0]
                    assert node["fields"]["effect"] == "bends local spacetime"
                    provenance = await client.get(
                        f"/api/v2/provenance/{node['node_id']}"
                    )
                    assert provenance.status_code == 200
                    effect = next(
                        item
                        for item in provenance.json()["items"]
                        if item["field_name"] == "effect"
                    )
                    assert effect["node_revision_id"] == node["revision_id"]
                    assert effect["exact_excerpt"] == excerpt
                    with Session(runtime.engine) as session:
                        fragment = session.get(EvidenceFragment, effect["fragment_id"])
                        revision = session.get(
                            SourceRevision, effect["source_revision_id"]
                        )
                        assert fragment.source_revision_id == revision.id
                        assert (
                            session.get(Source, revision.source_id).canonical_url
                            == "https://example.test/fusion"
                        )
                        assert runtime.blobs.get(revision.blob_hash) == excerpt.encode()
                        for model, count in (
                            (CanonNode, 1),
                            (CanonNodeRevision, 1),
                            (IntegrationEffect, 1),
                            (SourceRevision, 1),
                            (EvidenceFragment, 2),
                            (ModelStepEffect, 5),
                            (ModelCall, 5),
                        ):
                            assert (
                                session.scalar(select(func.count()).select_from(model))
                                == count
                            )
                    assert model_calls == (
                        ["research.plan"] if transient_failure else []
                    ) + list(values)
                    assert source_calls.count("/fusion") == 1
        assert runtime.worker.stop_event.is_set()
        assert runtime.worker._tasks == []
        assert all(
            task.done() and not task.cancelled() and task.exception() is None
            for task in worker_tasks
        )
        assert outbound.is_closed
