import asyncio
import json
from typing import Any

from sqlalchemy import text
from sqlmodel import Session, select

from app.core.acquisition_cache import acquisition_cache
from app.core.context import get_current_universe
from app.core.importers.ocr_importer import ocr_importer
from app.core.web_fetch import web_fetcher
from app.core.web_search import web_searcher
from app.db.schema import (
    Artifact,
    ArtifactVersion,
    Evidence,
    EvidenceChunk,
    Universe,
)
from app.services.predicate_service import PredicateService
from app.db.session import engine
from app.db.unconfirmed_schema import (
    AcquisitionArtifact,
    NotebookEntry,
    UnconfirmedUniverse,
)
from app.db.unconfirmed_session import unconfirmed_engine
from app.services.knowledge_retriever import KnowledgeRetrieverService
from app.services.research_workspace import WorkspaceService
from app.services.universe_service import UniverseService


async def tool_load_notebook_entry(args: dict[str, Any]) -> str:
    entry_id = args.get("entry_id")
    if not entry_id:
        return "Error: Missing entry_id."

    service = WorkspaceService()
    entry = service.get_notebook_entry(entry_id)
    if not entry:
        return f"Notebook entry {entry_id} not found."

    return (
        f"--- Notebook Entry {entry.id} ---\n"
        f"Title: {entry.title}\n"
        f"Kind: {entry.kind} | Status: {entry.status} | Priority: {entry.priority}\n"
        f"Summary: {entry.summary}\n"
        f"Details: {entry.details or 'No detailed notes provided.'}"
    )


async def tool_delete_notebook_entry(args: dict[str, Any]) -> str:
    entry_id = args.get("entry_id")
    if not entry_id:
        return "Error: Missing entry_id."

    service = WorkspaceService()
    if service.delete_notebook_entry(entry_id):
        return f"Notebook entry {entry_id} deleted successfully."
    return f"Notebook entry {entry_id} not found."

async def tool_save_notebook_entry(args: dict[str, Any]) -> str:
    universe_uuid = _get_universe_uuid()
    if not universe_uuid:
        return "Error: No active universe context."

    entry_id = args.get("entry_id")
    title = args.get("title")
    summary = args.get("summary")
    kind = args.get("kind", "Observation")
    details = args.get("details")
    status = args.get("status", "OPEN")
    priority = args.get("priority", 0)

    if not title or not summary:
        return "Error: Missing title or summary."

    service = WorkspaceService()
    entry = service.upsert_notebook_entry(
        universe_uuid=universe_uuid,
        title=title,
        summary=summary,
        kind=kind,
        details=details,
        status=status,
        priority=priority,
        entry_id=entry_id
    )
    return f"Notebook entry {entry.id} saved successfully."


async def tool_manage_source(args: dict[str, Any]) -> str:
    universe_uuid = _get_universe_uuid()
    if not universe_uuid:
        return "Error: No active universe context."

    url = args.get("url")
    if not url:
        return "Error: Missing url."

    title = args.get("title")
    reason = args.get("reason_saved")
    coverage = args.get("coverage")
    reliability = args.get("reliability")
    status = args.get("extraction_status", "UNREAD")
    source_id = args.get("source_id")

    service = WorkspaceService()
    source = service.upsert_source(
        universe_uuid=universe_uuid,
        url=url,
        title=title,
        reason_saved=reason,
        coverage=coverage,
        reliability=reliability,
        extraction_status=status,
        source_id=source_id
    )
    return f"Source {source.id} updated/saved: {source.url}"


async def tool_record_timeline_event(args: dict[str, Any]) -> str:
    universe_uuid = _get_universe_uuid()
    if not universe_uuid:
        return "Error: No active universe context."

    title = args.get("title")
    if not title:
        return "Error: Missing title."

    date = args.get("date")
    era = args.get("era")
    summary = args.get("summary")
    description = args.get("description")
    importance = args.get("importance", 1)
    confidence = args.get("confidence", 1.0)

    service = WorkspaceService()
    event = service.create_timeline_event(
        universe_uuid=universe_uuid,
        title=title,
        date=date,
        era=era,
        summary=summary,
        description=description,
        importance=importance,
        confidence=confidence
    )
    return f"Timeline event {event.id} recorded: {title}"


async def tool_add_timeline_detail(args: dict[str, Any]) -> str:
    timeline_id = args.get("timeline_id")
    if not timeline_id:
        return "Error: Missing timeline_id."

    detail_type = args.get("type") # 'participant', 'location', 'source', 'claim'
    value_id = args.get("value_id")
    role = args.get("role") # for participants

    if not value_id:
        return "Error: Missing value_id."

    service = WorkspaceService()
    if detail_type == "participant":
        service.add_timeline_participant(timeline_id, value_id, role)
    elif detail_type == "location":
        service.add_timeline_location(timeline_id, value_id)
    elif detail_type == "source":
        service.add_timeline_source(timeline_id, value_id)
    else:
        return f"Error: Invalid detail type '{detail_type}'."

    return f"Added {detail_type} {value_id} to timeline event {timeline_id}."


async def tool_web_search(args: dict[str, Any]) -> str:
    queries = args.get("queries", [])
    if not queries:
        single_query = args.get("search_query")
        if not single_query:
            return "Error: Missing search_query or queries argument."
        queries = [single_query]

    engines_arg = args.get("engine", "duckduckgo")
    if isinstance(engines_arg, str):
        engines = [e.strip().lower() for e in engines_arg.split(",")]
    elif isinstance(engines_arg, list):
        engines = [
            e.strip().lower() if isinstance(e, str) else str(e) for e in engines_arg
        ]
    else:
        engines = ["duckduckgo"]

    site_filter = args.get("site_filter")
    max_results = args.get("max_results", 10)

    async def run_search(q, eng):
        url = f"search:{eng}:{q}|site:{site_filter}|max:{max_results}"
        async def fetch_func():
            res = await web_searcher.perform_search(
                q, engine=eng, site_filter=site_filter, max_results=max_results
            )
            return AcquisitionArtifact(
                content_hash=AcquisitionArtifact.compute_hash(
                    json.dumps(res, default=str)
                ),
                source_url=url,
                content_type="search_result",
                extracted_text=json.dumps(res, default=str),
                engine_name=eng,
            )

        artifact, _ = await acquisition_cache.get(url, do_fetch=fetch_func)
        res = json.loads(artifact.extracted_text) if artifact else None
        return (q, eng, res)

    tasks = []
    for q in queries:
        for eng in engines:
            tasks.append(run_search(q, eng))

    results = await asyncio.gather(*tasks)

    # Group results by query
    query_results = {q: [] for q in queries}
    for q, eng, res in results:
        query_results[q].append((eng, res))

    output_blocks = []
    for i, q in enumerate(queries, 1):
        q_block = [f"### Query {i}: {q}"]

        engine_outputs = []
        for eng, res in query_results[q]:
            if not res or isinstance(res, str):
                engine_outputs.append(f"**{eng}**: {res or 'No result'}")
                continue

            status = res.get("status")
            if status == "ERROR":
                engine_outputs.append(f"**{eng}**: Error: {res.get('message')}")
            elif status == "BLOCKED":
                engine_outputs.append(f"**{eng}**: [BLOCKED] {res.get('message')}")
            elif status == "NO_RESULTS":
                engine_outputs.append(
                    f"**{eng}**: No results found. {res.get('message')}"
                )
            elif status == "SUCCESS":
                search_results = res.get("results", [])
                res_list = [
                    f"{j}. [{r['title']}]({r['url']})\n{r['snippet']}"
                    for j, r in enumerate(search_results, 1)
                ]
                engine_outputs.append(
                    f"**{eng}**:\n"
                    + ("\n\n".join(res_list) if res_list else "No results parsed.")
                )
            else:
                engine_outputs.append(f"**{eng}**: Unexpected status {status}")

        q_block.append("\n\n".join(engine_outputs))
        output_blocks.append("\n".join(q_block))

    output = "\n\n---\n\n".join(output_blocks)

    return output


def _get_run_id() -> str | None:
    from app.core.runtime_state import get_current_run_id
    return get_current_run_id()



def _get_universe_uuid() -> str | None:
    ctx = get_current_universe()
    if not ctx:
        return None
    service = UniverseService()
    uni = service.get_universe(ctx)
    if uni:
        return uni.uuid
    return None


def _store_artifact(
    content_type: str,
    content_text: str,
    source_url: str,
    engine_name: str | None = None,
) -> int | None:
    content_hash = AcquisitionArtifact.compute_hash(content_text)
    existing = acquisition_cache.repo.get_by_hash(content_hash)
    if existing and existing.id is not None:
        return existing.id

    artifact = AcquisitionArtifact(
        content_hash=content_hash,
        source_url=source_url,
        content_type=content_type,
        extracted_text=content_text[:100000],
        engine_name=engine_name,
    )
    stored = acquisition_cache.repo.store(artifact)
    if stored.id is not None:
        universe_uuid = _get_universe_uuid()
        run_id = _get_run_id()
        if universe_uuid and run_id:
                try:
                    acquisition_cache.repo.record_usage(
                        artifact_id=stored.id,
                        universe_uuid=universe_uuid,
                        run_id=run_id,
                    )
                except Exception as e:
                    import logging
                    logging.getLogger("tools").error(f"Failed to record artifact usage: {e!s}")

    return stored.id


async def tool_fetch_page(args: dict[str, Any]) -> str:
    urls = args.get("urls", [])
    if not urls or not isinstance(urls, list):
        if isinstance(urls, str):
            urls = [urls]
        else:
            return "Error: Missing or invalid urls argument (expected list)."

    max_links = args.get("max_links", 20)

    async def run_fetch(url):
        async def do_fetch():
            res = await web_fetcher.fetch_page(url, max_links=max_links)
            return AcquisitionArtifact(
                content_hash=AcquisitionArtifact.compute_hash(json.dumps(res, default=str)),
                source_url=url,
                content_type="web_page",
                extracted_text=json.dumps(res, default=str),
                engine_name="trafilatura",
            )

        try:
            artifact, status = await acquisition_cache.get(url, do_fetch=do_fetch)
            if not artifact:
                return (f"Error fetching {url}: fetch failed", None, "fetch_failed", None)

            res = json.loads(artifact.extracted_text)

            if isinstance(res, str): # Should not happen with current web_fetcher
                 return (f"--- Content from {url} ---\n{res}", res, "fetch_failed", None)

            if "error" in res:
                return (f"Error fetching {url}: {res['error']}", res, "fetch_failed", artifact)

            meta = res["metadata"]
            output = [
                f"--- Content from {url} (Artifact ID: {artifact.id}) ---",
                f"[EXTRACTION REPORT]\nWords: {meta['word_count']} | Type: {meta['page_type']}",
            ]


            if res.get("freshness"):
                output.append(res["freshness"])

            output.append("[MAIN ARTICLE]\n" + res["main_content"])

            if res.get("internal_links"):
                links = res["internal_links"]
                recommended = [link for link in links if link["tier"] == "High"]
                others = [link for link in links if link["tier"] != "High"]

                links_output = []
                if recommended:
                    links_output.append("### RECOMMENDED NEXT STEPS (High Value)")
                    links_output.extend(
                        [
                            f"- {link['title']} [{link['tier']} | {link['score']}x | {', '.join(link['sections']) or 'General'}]({link['url']})"
                            for link in recommended
                        ]
                    )

                if others:
                    links_output.append("\n### OTHER INTERNAL LINKS")
                    links_output.extend(
                        [
                            f"- {link['title']} [{link['tier']} | {link['score']}x | {', '.join(link['sections']) or 'General'}]({link['url']})"
                            for link in others
                        ]
                    )

                output.append("[INTERNAL LINKS]\n" + "\n".join(links_output))

            if res.get("research_signals"):
                output.append("[RESEARCH SIGNALS]\n" + res["research_signals"])

            return ("\n\n".join(output), res, status, artifact)
        except Exception as e:
            return (f"Error fetching {url}: {e!s}", None, "fetch_failed", None)

    fetch_results = await asyncio.gather(*[run_fetch(url) for url in urls])

    output_parts = []
    for output_str, _, _, _ in fetch_results:
        output_parts.append(output_str)

    output = "\n\n".join(output_parts)

    # Record usage for actual fetches
    universe_uuid = _get_universe_uuid()
    run_id = _get_run_id()
    if universe_uuid and run_id:
        for _, _, status, artifact in fetch_results:
            if status == "fetched" and artifact:
                try:
                    acquisition_cache.repo.record_usage(
                        artifact_id=artifact.id,
                        universe_uuid=universe_uuid,
                        run_id=run_id,
                        usage_type="direct_fetch"
                    )
                except Exception as e:
                    import logging
                    logging.getLogger("tools").error(f"Failed to record fetch usage: {e!s}")

    return output


def build_freshness_comparison_report(url_content_map: dict[str, str | None]) -> str:
    """
    Pure formatter: takes {url: content_or_None} and produces the comparison
    report. Kept separate from fetching so the agent loop can supply content
    that was already read through the shared, budgeted page-fetch path
    (see agent_engine.py) instead of this tool fetching pages on its own
    and silently bypassing the per-run fetch budget/cache.
    """
    reports = []
    for url, content in url_content_map.items():
        if content is None:
            reports.append(
                f"CANDIDATE: {url}\nUnavailable (fetch budget exhausted or fetch failed)."
            )
            continue

        # Handle cases where content might be a dict instead of a str
        if isinstance(content, dict):
            content = content.get("main_content", str(content))

        if "[END SIGNALS]" in content:
            signal_block = content.split("[END SIGNALS]")[0] + "[END SIGNALS]"
        else:
            try:
                signal_block = content[:500]
            except Exception as e:
                raise TypeError(
                    f"Failed to slice content for {url}. Content type: {type(content)}. Error: {e}"
                )
        reports.append(f"CANDIDATE: {url}\n{signal_block}")

    return (
        "Compare these candidates. Prefer sources with NO staleness warning, "
        "a recent Last-Modified/'last edited' signal, and no unresolved 'moved' notice. "
        "A source that a redirect or canonical tag points AWAY from is likely the stale one, "
        "even if it ranked first in search results.\n\n" + "\n\n".join(reports)
    )


async def tool_compare_source_freshness(args: dict[str, Any]) -> str:
    """
    Standalone/direct-use form: fetches each candidate URL itself (no shared
    cache/budget). Used for direct calls and tests. When this tool is invoked
    through the normal agent loop, agent_engine.py intercepts it before it
    reaches here and instead performs budgeted, cached fetches, then calls
    build_freshness_comparison_report() directly — see the "compareSourceFreshness"
    branch in agent_engine.py's tool dispatch.
    """
    urls = args.get("urls", [])
    if not urls or not isinstance(urls, list):
        return "Error: Missing or invalid urls argument (expected a list of at least 2 URLs)."

    url_content_map = {}
    for url in urls:
        try:
            url_content_map[url] = await web_fetcher.fetch_page(
                url, include_freshness=True
            )
        except Exception:
            url_content_map[url] = None

    return build_freshness_comparison_report(url_content_map)


async def tool_query_claims(args: dict[str, Any]) -> str:
    universe_name = get_current_universe()
    if not universe_name:
        return "Error: No active universe context."

    predicate_filter = args.get("predicate")

    with Session(engine) as session:
        universe = session.exec(
            select(Universe).where(Universe.name == universe_name)
        ).first()
        if not universe:
            return f"Universe {universe_name} not found."

        retriever = KnowledgeRetrieverService(session)
        claims = retriever.get_semantic_claims(universe.id, predicate_filter=predicate_filter)
        
        if not claims:
            return f"No verified claims found for {universe_name} matching filter '{predicate_filter or 'any'}'."

        lines = [
            f"({c['subject']} --{c['predicate']}--> {c['object']}) | support: {c['support']} | ref: {c['reference'] or 'N/A'}"
            for c in claims
        ]
        return "\n".join(lines)

async def tool_delete_unconfirmed_claim(args: dict[str, Any]) -> str:
    return "No unconfirmed atomic claims found in the research workspace."

async def tool_query_unconfirmed_claims(args: dict[str, Any]) -> str:
    return "No unconfirmed atomic claims found in the research workspace."

async def tool_query_unconfirmed_artifacts(args: dict[str, Any]) -> str:
    return "No unconfirmed artifacts found in the research workspace."

async def tool_delete_unconfirmed_artifact(args: dict[str, Any]) -> str:
    return "No unconfirmed artifacts found to delete."

async def tool_delete_artifact(args: dict[str, Any]) -> str:
    universe_name = get_current_universe()
    if not universe_name:
        return "Error: No active universe context."

    artifact_id = args.get("artifact_id")
    if not artifact_id:
        return "Error: Missing artifact_id."

    with Session(engine) as session:
        universe = session.exec(select(Universe).where(Universe.name == universe_name)).first()
        if not universe:
            return f"Universe {universe_name} not found."
        
        art = session.get(Artifact, artifact_id)
        if not art or art.universe_id != universe.id:
            return f"Artifact {artifact_id} not found in {universe_name}."
        
        session.delete(art)
        session.commit()
        return f"Artifact {artifact_id} deleted successfully."

async def tool_upsert_artifacts(args: dict[str, Any]) -> str:
    """
    Integrates polymorphic artifacts (Entity, Claim, Event, Specification) into the permanent records.
    Expects `items`: [{type, name, confidence, freshness, source_reference, source_wiki, payload}, ...].
    """
    universe_name = get_current_universe()
    if not universe_name:
        return "Error: No active universe context."

    items = args.get("items")
    if not items:
        return "Error: Missing `items` list."

    pred_service = PredicateService()

    with Session(engine) as session:
        session.execute(text("BEGIN IMMEDIATE"))
        universe = session.exec(
            select(Universe).where(Universe.name == universe_name)
        ).first()
        if not universe:
            return f"Universe {universe_name} not found."

        def get_or_create_artifact(name: str, art_type: str, payload: dict = None):
            # 1. Try to find by name and type
            art = session.exec(
                select(Artifact).where(
                    Artifact.universe_id == universe.id,
                    Artifact.type == art_type,
                    Artifact.name == name
                )
            ).first()
            if art:
                return art
            
            # 2. Try to find by payload (Merge duplicate factual content)
            if payload:
                payload_str = json.dumps(payload, sort_keys=True)
                art = session.exec(
                    select(Artifact).where(
                        Artifact.universe_id == universe.id,
                        Artifact.type == art_type,
                        Artifact.payload_json == payload_str
                    )
                ).first()
                if art:
                    # Merge: update name to the new name and return
                    art.name = name
                    session.add(art)
                    session.flush()
                    return art
            
            # 3. Create new
            art = Artifact(
                name=name,
                type=art_type,
                universe_id=universe.id
            )
            session.add(art)
            session.flush()
            return art

        created, updated = [], []

        for item in items:
            art_type = item.get("type")
            name = item.get("name")
            conf = item.get("confidence")
            fresh = item.get("freshness")
            ref = item.get("source_reference")
            wiki = item.get("source_wiki")
            payload = item.get("payload", {})

            if not art_type or not name:
                continue

            existing_art = session.exec(
                select(Artifact).where(
                    Artifact.universe_id == universe.id,
                    Artifact.type == art_type,
                    Artifact.name == name
                )
            ).first()

            is_new = existing_art is None
            art = get_or_create_artifact(name, art_type, payload)

            # Handle Evidence Deduplication (URL + Section)
            evidence_ids = []
            if ref or wiki:
                url = wiki or ref
                section = item.get("section", "General")
                
                existing_ev = session.exec(
                    select(Evidence).where(
                        Evidence.universe_id == universe.id,
                        Evidence.source_url == url,
                        Evidence.section == section
                    )
                ).first()
                
                if existing_ev:
                    evidence_ids.append(existing_ev.id)
                else:
                    evidence = Evidence(
                        universe_id=universe.id,
                        source_url=url,
                        section=section,
                        source_name=wiki or "Unknown"
                    )
                    session.add(evidence)
                    session.flush()
                    evidence_ids.append(evidence.id)
                    
                    chunk = EvidenceChunk(
                        evidence_id=evidence.id,
                        content=ref or "",
                        chunk_index=0
                    )
                    session.add(chunk)
                    session.flush()

            art.confidence = conf
            art.freshness = fresh
            art.source_reference = ref
            art.source_wiki = wiki
            art.evidence_refs = json.dumps(evidence_ids)
            art.support_count = len(evidence_ids)
            
            if art_type == "claim":
                raw_pred = payload.get("predicate", "related_to")
                norm_pred = pred_service.normalize(raw_pred)
                subj_name = payload.get("subject")
                obj_name = payload.get("object")
                if not subj_name or not obj_name:
                    continue
                subj_art = get_or_create_artifact(subj_name, "entity")
                obj_art = get_or_create_artifact(obj_name, "entity")
                payload_data = {
                    "subject_id": subj_art.id,
                    "subject_name": subj_name,
                    "object_id": obj_art.id,
                    "object_literal": obj_name,
                    "predicate": norm_pred,
                    "attributes": payload.get("attributes", {})
                }
                art.payload_json = json.dumps(payload_data)
            elif art_type == "specification":
                parent_name = payload.get("parent")
                if not parent_name:
                    continue
                parent_art = get_or_create_artifact(parent_name, "entity")
                payload_data = {
                    "parent_id": parent_art.id,
                    "key": payload.get("key"),
                    "value": payload.get("value"),
                }
                art.payload_json = json.dumps(payload_data)
            elif art_type == "timeline_event":
                art.payload_json = json.dumps(payload)
            else:
                art.payload_json = json.dumps(payload)

            # Artifact Versioning (Internal Database Feature)
            if not is_new:
                from app.services.settings_service import SettingsService
                max_versions = int(SettingsService().get_setting("MAX_ARTIFACT_VERSIONS").value) if SettingsService().get_setting("MAX_ARTIFACT_VERSIONS") else 10
                
                # Archive current state to ArtifactVersion before updating
                # We use a separate session or flush to ensure current is captured
                old_version = session.exec(
                    select(ArtifactVersion)
                    .where(ArtifactVersion.artifact_id == art.id)
                    .order_by(ArtifactVersion.version.desc())
                ).first()
                
                new_ver_num = (old_version.version + 1) if old_version else 1
                
                # Create version record
                version_record = ArtifactVersion(
                    artifact_id=art.id,
                    version=new_ver_num,
                    payload_json=art.payload_json,
                    evidence_refs=art.evidence_refs
                )
                session.add(version_record)
                
                # Prune old versions
                if new_ver_num > max_versions:
                    session.exec(
                        select(ArtifactVersion).where(
                            ArtifactVersion.artifact_id == art.id,
                            ArtifactVersion.version <= new_ver_num - max_versions
                        )
                    ).delete()

            session.add(art)
            if is_new:
                created.append(name)
            else:
                updated.append(name)

            # Promote from Notebook: If notebook_entry_id is provided, delete the entry
            entry_id = item.get("notebook_entry_id")
            if entry_id:
                workspace_service = WorkspaceService(session=session)
                workspace_service.delete_notebook_entry(entry_id)

        session.commit()
        return f"Integrated {len(created)} new and {len(updated)} updated artifacts for {universe_name}."

async def tool_query_artifacts(args: dict[str, Any]) -> str:
    universe_name = get_current_universe()
    if not universe_name:
        return "Error: No active universe context."

    predicate_filter = args.get("predicate")

    with Session(engine) as session:
        universe = session.exec(
            select(Universe).where(Universe.name == universe_name)
        ).first()
        if not universe:
            return f"Universe {universe_name} not found."

        retriever = KnowledgeRetrieverService(session)
        graph = retriever.get_universe_knowledge_graph(universe.id)

        if not graph:
            return f"No verified claims found for {universe_name}."

        output_blocks = []
        for entity, data in graph.items():
            # Filter facts if predicate_filter is provided
            filtered_facts = [
                f
                for f in data["facts"]
                if not predicate_filter or f["predicate"] == predicate_filter
            ]

            if not filtered_facts:
                continue

            # Reconstruct a Fact Sheet for this entity
            block = [f"Entity: {entity}"]

            facts_lines = []
            total_support = 0
            for f in filtered_facts:
                facts_lines.append(
                    f"- {f['predicate'].replace('_', ' ').title()}: {f['object']} (support: {f['support']})"
                )
                total_support += f["support"]

            block.append("Verified Facts:")
            block.extend(facts_lines)

            if data["related_entities"]:
                block.append("Related Entities:")
                block.append(", ".join(data["related_entities"]))

            avg_conf = total_support / len(filtered_facts) if filtered_facts else 0
            block.append(f"Confidence: {avg_conf:.1f} avg supporting sources")

            output_blocks.append("\n".join(block))

        if not output_blocks:
            return f"No verified claims found for {universe_name} matching filter '{predicate_filter}'."

        return "\n\n---\n\n".join(output_blocks)












async def tool_ocr_image(args: dict[str, Any]) -> str:
    image_url = args.get("image_url")
    image_data = args.get("image_data")
    preferred = args.get("preferred_engine")
    use_gpu = args.get("use_gpu")

    if not image_url and not image_data:
        return "Error: Provide either image_url or image_data."

    try:
        doc = await ocr_importer.fetch(
            image_url or "data:image/unknown;base64,",
            image_data=image_data,
            preferred_engine=preferred,
            use_gpu=use_gpu,
        )
        if doc.extracted_text:
            gpu_info = ""
            meta = doc.metadata or {}
            if meta.get("gpu"):
                gpu_info = " [GPU]"
            parts = [f"OCR result ({doc.engine_name}{gpu_info}):", doc.extracted_text]
            if doc.structured_data:
                parts.append(f"Structured data: {doc.structured_data}")
            return "\n\n".join(parts)
        return f"OCR returned no text. Status: {doc.content_type}. Engine: {doc.engine_name or 'none'}."
    except Exception as e:
        return f"OCR failed: {e!s}"


async def tool_link_universes(args: dict[str, Any]) -> str:
    """
    Defines a relationship between the active universe and another universe.
    Expected args: {target_universe_name, relation_type, description}.
    Relation types: 'PRECEDES' (timeline), 'ALTERNATE' (multiverse), 'SUBSET' (part of), 'PARENT'.
    """
    current_name = get_current_universe()
    target_name = args.get("target_universe_name")
    rel_type = args.get("relation_type")
    description = args.get("description")

    if not current_name or not target_name or not rel_type:
        return (
            "Error: Missing current_universe, target_universe_name, or relation_type."
        )

    service = UniverseService()
    with Session(engine) as session:
        u1 = session.exec(select(Universe).where(Universe.name == current_name)).first()
        u2 = session.exec(select(Universe).where(Universe.name == target_name)).first()

        if not u1 or not u2:
            return f"Error: One or both universes ({current_name}, {target_name}) not found."

        service.create_universe_relation(u1.id, u2.id, rel_type, description)
        return f"Linked {current_name} --{rel_type}--> {target_name}."


async def tool_link_entity_to_canonical(args: dict[str, Any]) -> str:
    """
    Links an entity in the active universe to a canonical version of that entity.
    Expected args: {entity_name, canonical_entity_id}.
    If canonical_entity_id is null, this entity is marked as the canonical version.
    """
    current_name = get_current_universe()
    entity_name = args.get("entity_name")
    canonical_id = args.get("canonical_entity_id")

    if not current_name or not entity_name:
        return "Error: Missing active universe context or entity_name."

    service = UniverseService()
    with Session(engine) as session:
        session.execute(text("BEGIN IMMEDIATE"))
        universe = session.exec(
            select(Universe).where(Universe.name == universe_name)
        ).first()
        if not universe:
            return f"Universe {current_name} not found."

        entity = session.exec(
            select(Artifact).where(
                Artifact.universe_id == universe.id,
                Artifact.type == "entity",
                Artifact.name == entity_name
            )
        ).first()
        if not entity:
            return f"Entity {entity_name} not found in {current_name}."

        # Resolve canonical_id if it's a name
        resolved_canonical_id = canonical_id
        if isinstance(canonical_id, str):
            canonical_entity = session.exec(
                select(Artifact).where(
                    Artifact.type == "entity",
                    Artifact.name == canonical_id
                )
            ).first()
            if not canonical_entity:
                return f"Canonical entity {canonical_id} not found in any universe."
            resolved_canonical_id = canonical_entity.id

        service.set_entity_canonical(entity.id, resolved_canonical_id)
        status = (
            "marked as canonical"
            if resolved_canonical_id is None
            else f"linked to canonical ID {resolved_canonical_id}"
        )
        return f"Entity {entity_name} in {current_name} {status}."


async def tool_delete_unconfirmed_claim(args: dict[str, Any]) -> str:
    """Accepts either a single `claim_id`, or a batch via `claim_ids`: [id, ...]."""
    claim_ids = args.get("claim_ids")
    if not claim_ids:
        single_id = args.get("claim_id")
        if not single_id:
            return "Error: Missing claim_id or claim_ids."
        claim_ids = [single_id]


    universe_name = get_current_universe()
    if not universe_name:
        return "Error: No active universe context."

    deleted, errors = [], []
    with Session(unconfirmed_engine) as session:
        universe = session.exec(
            select(UnconfirmedUniverse).where(UnconfirmedUniverse.name == universe_name)
        ).first()
        for claim_id in claim_ids:
            claim = session.get(UnconfirmedClaim, claim_id)
            if not claim:
                errors.append(f"{claim_id} not found")
                continue
            if not universe or claim.universe_id != universe.id:
                errors.append(f"{claim_id} does not belong to current universe")
                continue
            session.delete(claim)
            deleted.append(str(claim_id))
        session.commit()

    result = f"Deleted {len(deleted)} unconfirmed claim(s): {', '.join(deleted) if deleted else 'none'}."
    if errors:
        result += " Errors: " + "; ".join(errors)
    return result


AGENT_TOOLS: dict[str, dict[str, Any]] = {
    "webSearch": {
        "func": tool_web_search,
        "description": "Search the web for lore, technology, or cosmology. Returns results from specified engine. Supports batching via `queries`.",
        "parameters": {
            "type": "object",
            "properties": {
                "search_query": {
                    "type": "string",
                    "description": "The search query to use (single).",
                },
                "queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of search queries to execute in parallel.",
                },
                "engine": {
                    "type": "string",
                    "description": "Search engine to use (google, duckduckgo, brave).",
                    "default": "google",
                },
                "site_filter": {
                    "type": "string",
                    "description": "Restrict search to a specific domain (e.g. 'fandom.com').",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Number of results to return per query.",
                    "default": 10,
                },
            },
            "required": [],
        },
    },
    "fetchPage": {
        "func": tool_fetch_page,
        "description": "Fetch and read the full text of a specific URL. Reads are cached and count against a shared per-run fetch budget (also shared with compareSourceFreshness). Returns structured content including the main article, a scored list of internal research leads (links), and metadata. You can specify `max_links` to get more or fewer internal links.",
        "parameters": {
            "type": "object",
            "properties": {
                "urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of URLs to fetch.",
                },
                "url": {"type": "string", "description": "A single URL to fetch."},
                "max_links": {
                    "type": "integer",
                    "description": "Maximum number of internal research links to return. Default is 20.",
                    "default": 20,
                },
            },
            "required": [],
        },
    },
    "compareSourceFreshness": {
        "func": tool_compare_source_freshness,
        "description": "Compare 2+ candidate URLs for the same subject and report which is actively maintained vs. stale/moved/archived, using HTTP headers, on-page 'last edited' text, and redirect/canonical signals. Use this whenever webSearch surfaces more than one plausible wiki for the same universe, BEFORE settling on a canonical domain. Shares the same per-run fetch budget/cache as fetchPage — comparing candidates you've already fetched costs nothing extra.",
        "parameters": {
            "type": "object",
            "properties": {
                "urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "2 or more candidate URLs covering the same subject/universe.",
                }
            },
            "required": ["urls"],
        },
    },
    "upsertArtifacts": {
        "func": tool_upsert_artifacts,
        "description": "Integrate validated polymorphic artifacts (Entity, Claim, Event, Specification) into the permanent records. Prefer batching via `items`.",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "List of artifacts to integrate.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "description": (
                                    "entity | claim | timeline_event | "
                                    "specification"
                                ),
                            },
                            "name": {
                                "type": "string",
                                "description": "Identifier for the artifact.",
                            },
                            "confidence": {"type": "string"},
                            "freshness": {"type": "string"},
                            "source_reference": {"type": "string"},
                            "source_wiki": {"type": "string"},
                            "notebook_entry_id": {"type": "integer", "description": "ID of the notebook entry being promoted, if any."},
                            "payload": {
                                "type": "object",
                                "description": "Type-specific metadata.",
                            }
                        },
                        "required": ["type"]
                    }
                }
            }
        },
    },
    "deleteArtifact": {
        "func": tool_delete_artifact,
        "description": "Delete an artifact from the permanent records by ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "artifact_id": {"type": "integer", "description": "The ID of the artifact to delete."},
            },
            "required": ["artifact_id"],
        },
    },
    "queryClaims": {
        "func": tool_query_claims,

        "description": "Query verified claims from the main database for the current universe. Optionally filter by a specific predicate.",
        "parameters": {
            "type": "object",
            "properties": {
                "predicate": {
                    "type": "string",
                    "description": "The predicate to filter by.",
                }
            },
            "required": [],
        },
    },
    "queryUnconfirmedClaims": {
        "func": tool_query_unconfirmed_claims,
        "description": "Retrieve all unconfirmed atomic claims (S-P-O) for the active universe.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "queryUnconfirmedArtifacts": {
        "func": tool_query_unconfirmed_artifacts,
        "description": "Retrieve all unconfirmed artifacts from the research workspace for the active universe.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "linkUniverses": {
        "func": tool_link_universes,

        "description": "Define a relationship between the active universe and another universe. Use this for timelines, alternate realities, or nested cosmologies.",
        "parameters": {
            "type": "object",
            "properties": {
                "target_universe_name": {
                    "type": "string",
                    "description": "The name of the related universe.",
                },
                "relation_type": {
                    "type": "string",
                    "description": "The type of relation: 'PRECEDES' (chronological), 'ALTERNATE' (parallel), 'SUBSET' (contained within), 'PARENT' (source universe).",
                },
                "description": {
                    "type": "string",
                    "description": "Optional explanation of the relationship.",
                },
            },
            "required": ["target_universe_name", "relation_type"],
        },
    },
    "linkEntityToCanonical": {
        "func": tool_link_entity_to_canonical,
        "description": "Link an entity in the current universe to a canonical version of that entity. If canonical_entity_id is omitted or null, the entity is marked as the canonical reference for others.",
        "parameters": {
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "The name of the entity to link.",
                },
                                "canonical_entity_id": {
                                    "type": "string",
                                    "description": "The name or ID of the canonical entity. Pass null to mark this entity as canonical.",
                                },
            },
            "required": ["entity_name"],
        },
    },
    "deleteUnconfirmedClaim": {
        "func": tool_delete_unconfirmed_claim,
        "description": "Delete unconfirmed claim(s) by ID for the active universe.",
        "parameters": {
            "type": "object",
            "properties": {
                "claim_id": {
                    "type": "integer",
                    "description": "Single-item mode: the ID of the unconfirmed claim to delete.",
                },
                "claim_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Batch mode (preferred): all IDs to delete in one call.",
                },
            },
            "required": [],
        },
    },
    "loadNotebookEntry": {
        "func": tool_load_notebook_entry,
        "description": "Fetch the full details of a specific research notebook entry by ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "entry_id": {"type": "integer", "description": "The ID of the notebook entry to load."},
            },
            "required": ["entry_id"],
        },
    },
    "saveNotebookEntry": {
        "func": tool_save_notebook_entry,
        "description": "Create or update a research notebook entry (lead, hypothesis, etc.). Use this to record your current thinking, future tasks, and unresolved questions. Prefer updating existing entries via `entry_id` when refining a thought.",
        "parameters": {
            "type": "object",
            "properties": {
                "entry_id": {"type": "integer", "description": "ID of entry to update. Omit to create new."},
                "title": {"type": "string", "description": "Concise title for the entry."},
                "summary": {"type": "string", "description": "One-sentence summary of the core point."},
                "details": {"type": "string", "description": "Full detailed notes and reasoning."},
                "kind": {
                    "type": "string",
                    "enum": ["Lead", "Hypothesis", "Contradiction", "Question", "Observation"],
                    "description": "The nature of the entry."
                },
                "status": {
                    "type": "string",
                    "enum": ["OPEN", "RESOLVED", "SUPERSEDED", "DISCARDED"],
                    "description": "Current status of the investigation."
                },
                "priority": {"type": "integer", "description": "Priority level (0=Low, 10=Critical)."},
            },
            "required": ["title", "summary"],
        },
    },
    "deleteNotebookEntry": {
        "func": tool_delete_notebook_entry,
        "description": "Delete a research notebook entry by ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "entry_id": {"type": "integer", "description": "The ID of the notebook entry to delete."},
            },
            "required": ["entry_id"],
        },
    },
    "manageSource": {
        "func": tool_manage_source,
        "description": "Curate the research source library. Mark sources as useful, track their extraction status, and record why they are valuable.",
        "parameters": {
            "type": "object",
            "properties": {
                "source_id": {"type": "integer", "description": "ID of source to update. Omit to create new."},
                "url": {"type": "string", "description": "The URL of the source."},
                "title": {"type": "string", "description": "Title of the source."},
                "reason_saved": {"type": "string", "description": "Why this source is valuable for the research."},
                "coverage": {"type": "string", "description": "What specific aspects of the world it covers."},
                "reliability": {"type": "string", "description": "Assessment of source reliability."},
                "extraction_status": {
                    "type": "string",
                    "enum": ["UNREAD", "PARTIAL", "COMPLETE"],
                    "description": "How much of the source has been mined."
                },
            },
            "required": ["url"],
        },
    },
    "recordTimelineEvent": {
        "func": tool_record_timeline_event,
        "description": "Record a structured historical event in the world's timeline. This is for factual occurrences, not interpretations.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Name of the event."},
                "date": {"type": "string", "description": "Date of the event (e.g. '2183 CE')."},
                "era": {"type": "string", "description": "The era or period."},
                "summary": {"type": "string", "description": "Brief summary of the event."},
                "description": {"type": "string", "description": "Detailed account of what happened."},
                "importance": {"type": "integer", "description": "Impact level (1-10)."},
                "confidence": {"type": "number", "description": "Confidence in the event's occurrence (0.0-1.0)."},
            },
            "required": ["title"],
        },
    },
    "addTimelineDetail": {
        "func": tool_add_timeline_detail,
        "description": "Add a participant, location, source, or supporting claim to a timeline event.",
        "parameters": {
            "type": "object",
            "properties": {
                "timeline_id": {"type": "integer", "description": "ID of the timeline event."},
                "type": {
                    "type": "string",
                                    "enum": ["participant", "location", "source"],

                    "description": "The type of detail to add."
                },
                "value_id": {"type": "integer", "description": "The ID of the entity, source, or claim."},
                "role": {"type": "string", "description": "Role of the participant (e.g. 'Commander')."},
            },
            "required": ["timeline_id", "type", "value_id"],
        },
    },
    "executePlan": {
        "func": None,
        "description": "Execute a sequence of deterministic tool calls in a single turn to avoid redundant thinking loops. Use this for common patterns like Search -> Fetch first results -> Compare freshness. The plan should be a list of tool calls. You can reference results of previous steps using placeholders like $result_0, $result_1, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "plan": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "tool": {
                                "type": "string",
                                "description": "The name of the tool to call.",
                            },
                            "args": {
                                "type": "object",
                                "description": "The arguments for the tool. Can use $result_N placeholders.",
                            },
                        },
                        "required": ["tool", "args"],
                    },
                    "description": "The sequence of tool calls to execute.",
                }
            },
            "required": ["plan"],
        },
    },
    "ocrImage": {
        "func": tool_ocr_image,
        "description": "Extract text from an image using OCR (Optical Character Recognition). Pass an image URL or base64-encoded image data. Optionally specify a preferred OCR engine (docling, easyocr, tesseract, paddleocr). Defaults to best available engine. Returns extracted text and any structured content (headings, tables).",
        "parameters": {
            "type": "object",
            "properties": {
                "image_url": {
                    "type": "string",
                    "description": "URL of the image to process.",
                },
                "image_data": {
                    "type": "string",
                    "description": "Base64-encoded image bytes (alternative to image_url).",
                },
                "preferred_engine": {
                    "type": "string",
                    "description": "Optional: preferred OCR engine (docling, easyocr, tesseract, paddleocr).",
                    "enum": ["docling", "easyocr", "tesseract", "paddleocr"],
                },
                "use_gpu": {
                    "type": "boolean",
                    "description": "Optional: force GPU (true) or CPU (false). Default is auto-detect.",
                },
            },
            "required": [],
        },
    },
}
