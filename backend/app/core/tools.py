import asyncio
import json
from typing import Any

from sqlmodel import Session, select

from app.core.acquisition_cache import acquisition_cache
from app.core.context import get_current_universe
from app.core.web_fetch import web_fetcher
from app.core.web_search import web_searcher
from app.db.schema import (
    Claim,
    ClaimAttribute,
    Entity,
    EntityAlias,
    Evidence,
    EvidenceChunk,
    Predicate,
    Universe,
)
from app.db.session import engine
from app.db.unconfirmed_schema import (
    AcquisitionArtifact,
    UnconfirmedClaim,
    UnconfirmedUniverse,
)
from app.db.unconfirmed_session import unconfirmed_engine
from app.core.importers.ocr_importer import ocr_importer
from app.services.knowledge_retriever import KnowledgeRetrieverService
from app.services.predicate_service import PredicateService
from app.services.universe_service import UniverseService


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
            except Exception:
                pass
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
                except Exception:
                    pass

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


async def tool_upsert_claims(args: dict[str, Any]) -> str:
    """
    Integrates atomic claims (Subject, Context, Predicate, Object) into the permanent records.
    Expects `items`: [{subject, context, predicate, object_val, source_reference, source_wiki, confidence, attributes: {key: value}}, ...].
    """
    universe_name = get_current_universe()
    if not universe_name:
        return "Error: No active universe context."

    items = args.get("items")
    if not items:
        # support single claim for convenience
        items = [
            {
                "subject": args.get("subject", ""),
                "context": args.get("context"),
                "predicate": args.get("predicate", ""),
                "object_val": args.get("object_val", ""),
                "source_reference": args.get("source_reference"),
                "source_wiki": args.get("source_wiki"),
                "confidence": args.get("confidence", 0.0),
                "attributes": args.get("attributes", {}),
            }
        ]

    pred_service = PredicateService()

    with Session(engine) as session:
        universe = session.exec(
            select(Universe).where(Universe.name == universe_name)
        ).first()
        if not universe:
            return f"Universe {universe_name} not found."

        created, updated, skipped = [], [], []

        def get_or_create_entity(name: str, e_type: str = "Unknown"):
            entity = session.exec(
                select(Entity).where(
                    Entity.universe_id == universe.id, Entity.name == name
                )
            ).first()
            if not entity:
                alias = session.exec(
                    select(EntityAlias).where(
                        EntityAlias.universe_id == universe.id,
                        EntityAlias.alias == name,
                    )
                ).first()
                if alias:
                    entity = session.get(Entity, alias.entity_id)

            if not entity:
                entity = Entity(name=name, entity_type=e_type, universe_id=universe.id)
                session.add(entity)
                session.flush()
            return entity

        for item in items:
            s_name = item.get("subject", "")
            context = item.get("context")
            raw_pred = item.get("predicate", "")
            o_val = item.get("object_val", "")
            artifact_id = item.get("artifact_id")
            staging_ref = item.get("staging_ref")
            if not all([s_name, raw_pred, o_val]):
                skipped.append(f"Missing fields: {item}")
                continue

            # Evidence Layer: Link to structured evidence
            evidence_chunk_id = None
            source_wiki = item.get("source_wiki")
            source_ref = item.get("source_reference")

            if source_wiki:
                ev = session.exec(
                    select(Evidence).where(Evidence.source_url == source_wiki)
                ).first()
                if not ev:
                    ev = Evidence(
                        universe_id=universe.id,
                        source_url=source_wiki,
                        source_name=source_wiki,
                    )
                    session.add(ev)
                    session.flush()

                chunk = EvidenceChunk(
                    evidence_id=ev.id, content=source_ref or "Full page", chunk_index=0
                )
                session.add(chunk)
                session.flush()
                evidence_chunk_id = chunk.id

            # Normalization
            predicate_name = pred_service.normalize(raw_pred)
            pred_ent = session.exec(
                select(Predicate).where(Predicate.canonical_name == predicate_name)
            ).first()
            if not pred_ent:
                pred_ent = Predicate(canonical_name=predicate_name)
                session.add(pred_ent)
                session.flush()

            s_ent = get_or_create_entity(s_name)

            # Symmetric Entity Resolution for Object
            o_ent = session.exec(
                select(Entity).where(
                    Entity.universe_id == universe.id, Entity.name == o_val
                )
            ).first()
            if not o_ent:
                alias = session.exec(
                    select(EntityAlias).where(
                        EntityAlias.universe_id == universe.id,
                        EntityAlias.alias == o_val,
                    )
                ).first()
                if alias:
                    o_ent = session.get(Entity, alias.entity_id)
            
            if not o_ent:
                # If object isn't an existing entity, we treat it as a literal
                # but we could also auto-create it if we wanted. 
                # Following current logic: object_entity_id = None, object_literal = o_val
                o_ent = None

            o_entity_id = o_ent.id if o_ent else None
            o_literal = None if o_ent else o_val

            existing = session.exec(
                select(Claim).where(
                    Claim.subject_id == s_ent.id,
                    Claim.context == context,
                    Claim.predicate_id == pred_ent.id,
                    (Claim.object_entity_id == o_entity_id)
                    if o_entity_id
                    else (Claim.object_literal == o_literal),
                )
            ).first()

            if existing:
                existing.source_reference = source_ref or existing.source_reference
                existing.source_wiki = source_wiki or existing.source_wiki
                existing.evidence_chunk_id = (
                    evidence_chunk_id or existing.evidence_chunk_id
                )
                existing.support_count += 1
                session.add(existing)
                updated.append(f"({s_name}, {predicate_name}, {o_val})")
                target_claim = existing
            else:
                new_claim = Claim(
                    subject_id=s_ent.id,
                    context=context,
                    predicate_id=pred_ent.id,
                    predicate=predicate_name,
                    object_entity_id=o_entity_id,
                    object_literal=o_literal,
                    source_reference=source_ref,
                    source_wiki=source_wiki,
                    evidence_chunk_id=evidence_chunk_id,
                    support_count=1,
                    universe_scope=universe.id,
                    status="VERIFIED",
                    source_unconfirmed_id=staging_ref,
                )
                session.add(new_claim)
                session.flush()
                target_claim = new_claim

            # Attributes
            attrs = item.get("attributes", {})
            for k, v in attrs.items():
                attr = ClaimAttribute(claim_id=target_claim.id, key=k, value=str(v))
                session.add(attr)
                session.flush()  # get ID
                created.append(f"({s_name}, {predicate_name}, {o_val})")

            # Provenance
            if artifact_id:
                print(f"DEBUG: recording provenance for artifact {artifact_id}")
                run_id = _get_run_id()
                if run_id:
                    print(f"DEBUG: run_id is {run_id}")
                    try:
                        acquisition_cache.store_provenance(
                            source_artifact_id=artifact_id,
                            target_type="unconfirmed_claim",
                            target_id=new_claim.id,
                            relation="supports",
                            run_id=run_id,
                        )
                    except Exception as e:
                        print(f"DEBUG: provenance recording failed: {e}")
                else:
                    print("DEBUG: run_id is None, skipping provenance")


            # Handle attributes
            attrs = item.get("attributes", {})
            if isinstance(attrs, dict):
                for k, v in attrs.items():
                    # Use a composite key check or just append
                    # For now, we overwrite if key exists for this claim
                    existing_attr = session.exec(
                        select(ClaimAttribute).where(
                            ClaimAttribute.claim_id == target_claim.id,
                            ClaimAttribute.key == k,
                        )
                    ).first()
                    if existing_attr:
                        existing_attr.value = str(v)
                        session.add(existing_attr)
                    else:
                        session.add(
                            ClaimAttribute(
                                claim_id=target_claim.id, key=k, value=str(v)
                            )
                        )

        session.commit()

        parts = []
        if created:
            parts.append(f"Created: {len(created)} claims")
        if updated:
            parts.append(f"Updated: {len(updated)} claims")
        if skipped:
            parts.append(f"Skipped: {len(skipped)} items")
        return f"Integrated claims for {universe_name}: " + (
            "; ".join(parts) if parts else "no changes."
        )


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


async def tool_query_unconfirmed_claims(args: dict[str, Any]) -> str:
    universe_name = get_current_universe()
    if not universe_name:
        return "Error: No active universe context."

    with Session(unconfirmed_engine) as session:
        universe = session.exec(
            select(UnconfirmedUniverse).where(UnconfirmedUniverse.name == universe_name)
        ).first()
        if not universe:
            return f"No unconfirmed data for {universe_name}."

        claims = session.exec(
            select(UnconfirmedClaim).where(UnconfirmedClaim.universe_id == universe.id)
        ).all()
        if not claims:
            return f"No unconfirmed claims for {universe_name}."

        return "\n".join(
            [
                f"ID: {c.id} | subj: {c.subject} | pred: {c.predicate} | obj: {c.object_val} | ref: {c.reference or 'N/A'} | conf: {c.confidence or 'N/A'}"
                for c in claims
            ]
        )


async def tool_save_unconfirmed_claim(args: dict[str, Any]) -> str:
    """
    Save unconfirmed claims for the active universe.
    Claims are atomic statements: (subject, context, predicate, object).
    Prefer batching via `items`: [{subject, context, predicate, object_val, reference, wiki_source, confidence, artifact_id}, ...].
    """
    universe_name = get_current_universe()
    if not universe_name:
        return "Error: No active universe context."

    items = args.get("items")
    if not items:
        single = {
            "subject": args.get("subject", ""),
            "context": args.get("context"),
            "predicate": args.get("predicate", ""),
            "object_val": args.get("object_val", ""),
            "reference": args.get("reference"),
            "wiki_source": args.get("wiki_source"),
            "confidence": args.get("confidence"),
            "artifact_id": args.get("artifact_id"),
        }
        items = [single]

    saved, errors = [], []
    with Session(unconfirmed_engine) as session:
        universe = session.exec(
            select(UnconfirmedUniverse).where(UnconfirmedUniverse.name == universe_name)
        ).first()
        if not universe:
            universe = UnconfirmedUniverse(name=universe_name)
            session.add(universe)
            session.flush()

        for item in items:
            subject = item.get("subject", "")
            context = item.get("context")
            predicate = item.get("predicate", "")
            object_val = item.get("object_val", "")
            artifact_id = item.get("artifact_id")
            if not all([subject, predicate, object_val]):
                errors.append(f"Skipped claim with missing required fields: {item}")
                continue
            
            new_claim = UnconfirmedClaim(
                universe_id=universe.id,
                subject=subject,
                context=context,
                predicate=predicate,
                object_val=object_val,
                reference=item.get("reference"),
                wiki_source=item.get("wiki_source"),
                confidence=str(item.get("confidence") or ""),
            )
            session.add(new_claim)
            session.flush()

            if artifact_id:
                try:
                    acquisition_cache.store_provenance(
                        source_artifact_id=artifact_id,
                        target_type="unconfirmed_claim",
                        target_id=new_claim.id,
                        relation="supports",
                        run_id=_get_run_id(),
                        session=session,
                    )
                except Exception:
                    pass

            saved.append(new_claim.id)


        session.commit()

    result = f"Saved {len(saved)} unconfirmed claim(s) for {universe_name}. IDs: {', '.join(map(str, saved))}"
    if errors:
        result += " Errors: " + "; ".join(errors)
    return result


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
        universe = session.exec(
            select(Universe).where(Universe.name == current_name)
        ).first()
        if not universe:
            return f"Universe {current_name} not found."

        entity = session.exec(
            select(Entity).where(
                Entity.universe_id == universe.id, Entity.name == entity_name
            )
        ).first()
        if not entity:
            return f"Entity {entity_name} not found in {current_name}."

        # Resolve canonical_id if it's a name
        resolved_canonical_id = canonical_id
        if isinstance(canonical_id, str):
            canonical_entity = session.exec(
                select(Entity).where(
                    Entity.name == canonical_id
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
    "upsertClaims": {
        "func": tool_upsert_claims,
        "description": "Integrate atomic claims (Subject, Predicate, Object) into the permanent records. Use this to promote verified findings from the researcher. Prefer batching via `items`.",
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "The entity the claim is about.",
                },
                "predicate": {
                    "type": "string",
                    "description": "The relationship or property (e.g. 'is_a', 'located_in').",
                },
                "object_val": {
                    "type": "string",
                    "description": "The target entity or value.",
                },
                "source_reference": {
                    "type": "string",
                    "description": "URL and section reference.",
                },
                "source_wiki": {
                    "type": "string",
                    "description": "Wiki page name or URL.",
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score (0.0 to 1.0).",
                },
                "items": {
                    "type": "array",
                    "description": "Batch mode (preferred): a list of claims to integrate.",
                    "items": {
                        "type": "object",
                                 "properties": {
                                     "subject": {"type": "string"},
                                     "predicate": {"type": "string"},
                                     "object_val": {"type": "string"},
                                     "source_reference": {"type": "string"},
                                     "source_wiki": {"type": "string"},
                                     "confidence": {"type": "number"},
                                     "unconfirmed_claim_id": {"type": "integer", "description": "The ID of the staging claim this promotes."},
                                 },
                                 "required": ["subject", "predicate", "object_val"],
                                 },
                },
            },
            "required": [],
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
    "saveUnconfirmedClaim": {
        "func": tool_save_unconfirmed_claim,
        "description": "Save unconfirmed atomic claims (S-P-O) for the active universe. This is the primary way to persist granular knowledge. Prefer batching via `items`.",
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "The entity the claim is about.",
                },
                "predicate": {
                    "type": "string",
                    "description": "The relationship or property (e.g. 'is_a', 'located_in', 'has_power').",
                },
                "object_val": {
                    "type": "string",
                    "description": "The value or target entity of the claim.",
                },
                "reference": {
                    "type": "string",
                    "description": "URL and section reference.",
                },
                "wiki_source": {
                    "type": "string",
                    "description": "Wiki page name or URL.",
                },
                "confidence": {
                    "type": "string",
                    "description": "Confidence level (high, medium, low).",
                },
                "items": {
                    "type": "array",
                    "description": "Batch mode (preferred): a list of claims to save in one call.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "subject": {"type": "string"},
                            "predicate": {"type": "string"},
                            "object_val": {"type": "string"},
                            "reference": {"type": "string"},
                            "wiki_source": {"type": "string"},
                            "confidence": {"type": "string"},
                        },
                        "required": ["subject", "predicate", "object_val"],
                    },
                },
            },
            "required": [],
        },
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
