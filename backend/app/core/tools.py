from typing import Any, Dict, List, Optional
from sqlmodel import Session, select
from app.db.session import engine
from app.db.schema import Universe, Trait, Entity, Claim, ClaimAttribute, EntityAlias
from app.services.predicate_service import PredicateService
from app.db.unconfirmed_session import engine as unconfirmed_engine
from app.db.unconfirmed_schema import UnconfirmedUniverse, UnconfirmedTrait, UnconfirmedClaim
from app.core.web_search import web_searcher
from app.core.web_fetch import web_fetcher
from app.core.context import get_current_universe

async def tool_web_search(args: Dict[str, Any]) -> str:
    query = args.get("search_query", "")
    if not query:
        return "Error: Missing search_query argument."
    engine = args.get("engine", "duckduckgo")
    if isinstance(engine, str) and "," in engine:
        engine = engine.split(",")[0].strip().lower()
    site_filter = args.get("site_filter", None)
    return await web_searcher.perform_search(query, engine=engine, site_filter=site_filter)

async def tool_fetch_page(args: Dict[str, Any]) -> str:
    urls = args.get("urls", [])
    if not urls or not isinstance(urls, list):
        if isinstance(urls, str):
            urls = [urls]
        else:
            return "Error: Missing or invalid urls argument (expected list)."
    
    max_links = args.get("max_links", 20)
    
    results = []
    for url in urls:
        try:
            content = await web_fetcher.fetch_page(url, max_links=max_links)
            results.append(f"--- Content from {url} ---\n{content}")
        except Exception as e:
            results.append(f"Error fetching {url}: {str(e)}")

    return "\n\n".join(results)

def build_freshness_comparison_report(url_content_map: Dict[str, Optional[str]]) -> str:
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
            reports.append(f"CANDIDATE: {url}\nUnavailable (fetch budget exhausted or fetch failed).")
            continue
        if "[END SIGNALS]" in content:
            signal_block = content.split("[END SIGNALS]")[0] + "[END SIGNALS]"
        else:
            signal_block = content[:500]
        reports.append(f"CANDIDATE: {url}\n{signal_block}")

    return (
        "Compare these candidates. Prefer sources with NO staleness warning, "
        "a recent Last-Modified/'last edited' signal, and no unresolved 'moved' notice. "
        "A source that a redirect or canonical tag points AWAY from is likely the stale one, "
        "even if it ranked first in search results.\n\n" + "\n\n".join(reports)
    )


async def tool_compare_source_freshness(args: Dict[str, Any]) -> str:
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
            url_content_map[url] = await web_fetcher.fetch_page(url, include_freshness=True)
        except Exception as e:
            url_content_map[url] = None

    return build_freshness_comparison_report(url_content_map)


async def tool_query_universe_traits(args: Dict[str, Any]) -> str:
    universe_name = get_current_universe()
    if not universe_name:
        return "Error: No active universe context."

    with Session(engine) as session:
        universe = session.exec(select(Universe).where(Universe.name == universe_name)).first()
        if not universe:
            return f"Universe {universe_name} not found."

        traits = session.exec(select(Trait).where(Trait.universe_id == universe.id)).all()
        if not traits:
            return f"No traits currently found for {universe_name}."

        return "\n".join([f"ID: {t.id} | {t.name}: {t.value}" for t in traits])

async def tool_upsert_trait(args: Dict[str, Any]) -> str:
    """
    Accepts either a single trait via top-level name/value, or a batch via
    `items`: [{name, value}, ...]. Batching lets the DB Architect commit an
    entire world's worth of traits in one tool call instead of one round
    trip (and one LLM call) per trait.
    """
    universe_name = get_current_universe()
    if not universe_name:
        return "Error: No active universe context."

    items = args.get("items")
    if not items:
        items = [{"name": args.get("name", ""), "value": args.get("value", "")}]
        if not items[0]["name"]:
            return "Error: Missing trait name."

    with Session(engine) as session:
        universe = session.exec(select(Universe).where(Universe.name == universe_name)).first()
        if not universe:
            return f"Universe {universe_name} not found."

        updated, created, skipped = [], [], []
        for item in items:
            trait_name = item.get("name", "")
            trait_value = item.get("value", "")
            if not trait_name:
                skipped.append(str(item))
                continue
            trait = session.exec(select(Trait).where(Trait.universe_id == universe.id, Trait.name == trait_name)).first()
            if trait:
                trait.value = trait_value
                session.add(trait)
                updated.append(trait_name)
            else:
                session.add(Trait(universe_id=universe.id, name=trait_name, value=trait_value))
                created.append(trait_name)

        session.commit()

        parts = []
        if created:
            parts.append(f"Created: {', '.join(created)}")
        if updated:
            parts.append(f"Updated: {', '.join(updated)}")
        if skipped:
            parts.append(f"Skipped (missing name): {', '.join(skipped)}")
        return f"For {universe_name} — " + ("; ".join(parts) if parts else "no changes.")


async def tool_upsert_claims(args: Dict[str, Any]) -> str:
    """
    Integrates atomic claims (Subject, Predicate, Object) into the permanent records.
    Expects `items`: [{subject, predicate, object_val, source_reference, source_wiki, confidence, attributes: {key: value}}, ...].
    """
    universe_name = get_current_universe()
    if not universe_name:
        return "Error: No active universe context."

    items = args.get("items")
    if not items:
        # support single claim for convenience
        items = [{
            "subject": args.get("subject", ""),
            "predicate": args.get("predicate", ""),
            "object_val": args.get("object_val", ""),
            "source_reference": args.get("source_reference"),
            "source_wiki": args.get("wiki_source"),
            "confidence": args.get("confidence", 0.0),
            "attributes": args.get("attributes", {})
        }]

    pred_service = PredicateService()

    with Session(engine) as session:
        universe = session.exec(select(Universe).where(Universe.name == universe_name)).first()
        if not universe:
            return f"Universe {universe_name} not found."

        created, updated, skipped = [], [], []

        def get_or_create_entity(name: str, e_type: str = "Unknown"):
            entity = session.exec(select(Entity).where(Entity.universe_id == universe.id, Entity.name == name)).first()
            if not entity:
                alias = session.exec(select(EntityAlias).where(EntityAlias.universe_id == universe.id, EntityAlias.alias == name)).first()
                if alias:
                    entity = session.get(Entity, alias.entity_id)
            
            if not entity:
                entity = Entity(name=name, entity_type=e_type, universe_id=universe.id)
                session.add(entity)
                session.flush()
            return entity

        for item in items:
            s_name = item.get("subject", "")
            raw_pred = item.get("predicate", "")
            o_val = item.get("object_val", "")
            if not all([s_name, raw_pred, o_val]):
                skipped.append(f"Missing fields: {item}")
                continue

            # Normalization
            predicate_name = pred_service.normalize(raw_pred)
            pred_ent = session.exec(select(Predicate).where(Predicate.canonical_name == predicate_name)).first()
            if not pred_ent:
                pred_ent = Predicate(canonical_name=predicate_name)
                session.add(pred_ent)
                session.flush()
            
            s_ent = get_or_create_entity(s_name)
            
            # Determine if object is an entity or literal
            # In a real system, we might check if o_val is an existing entity or use an LLM
            # For now, we'll check if it exists as an entity in this universe.
            o_ent = session.exec(select(Entity).where(Entity.universe_id == universe.id, Entity.name == o_val)).first()
            
            o_entity_id = o_ent.id if o_ent else None
            o_literal = None if o_ent else o_val

            existing = session.exec(
                select(Claim).where(
                    Claim.subject_id == s_ent.id,
                    Claim.predicate_id == pred_ent.id,
                    (Claim.object_entity_id == o_entity_id) if o_entity_id else (Claim.object_literal == o_literal)
                )
            ).first()

            if existing:
                existing.source_reference = item.get("source_reference") or existing.source_reference
                existing.source_wiki = item.get("source_wiki") or existing.source_wiki
                existing.support_count += 1
                session.add(existing)
                updated.append(f"({s_name}, {predicate_name}, {o_val})")
                target_claim = existing
            else:
                new_claim = Claim(
                    subject_id=s_ent.id,
                    predicate_id=pred_ent.id,
                    predicate=predicate_name,
                    object_entity_id=o_entity_id,
                    object_literal=o_literal,
                    source_reference=item.get("source_reference"),
                    source_wiki=item.get("source_wiki"),
                    support_count=1,
                    universe_scope=universe.id,
                    status="VERIFIED"
                )
                session.add(new_claim)
                session.flush() # get ID
                created.append(f"({s_name}, {predicate_name}, {o_val})")
                target_claim = new_claim

            # Handle attributes
            attrs = item.get("attributes", {})
            if isinstance(attrs, dict):
                for k, v in attrs.items():
                    # Use a composite key check or just append
                    # For now, we overwrite if key exists for this claim
                    existing_attr = session.exec(select(ClaimAttribute).where(
                        ClaimAttribute.claim_id == target_claim.id, 
                        ClaimAttribute.key == k
                    )).first()
                    if existing_attr:
                        existing_attr.value = str(v)
                        session.add(existing_attr)
                    else:
                        session.add(ClaimAttribute(claim_id=target_claim.id, key=k, value=str(v)))

        session.commit()

        parts = []
        if created: parts.append(f"Created: {len(created)} claims")
        if updated: parts.append(f"Updated: {len(updated)} claims")
        if skipped: parts.append(f"Skipped: {len(skipped)} items")
        return f"Integrated claims for {universe_name}: " + ("; ".join(parts) if parts else "no changes.")


async def tool_query_unconfirmed_traits(args: Dict[str, Any]) -> str:
    universe_name = get_current_universe()
    if not universe_name:
        return "Error: No active universe context."

    with Session(unconfirmed_engine) as session:
        universe = session.exec(select(UnconfirmedUniverse).where(UnconfirmedUniverse.name == universe_name)).first()
        if not universe:
            return f"No unconfirmed data for {universe_name}."

        traits = session.exec(
            select(UnconfirmedTrait).where(UnconfirmedTrait.universe_id == universe.id)
        ).all()
        if not traits:
            return f"No unconfirmed traits for {universe_name}."

        return "\n".join([
            f"ID: {t.id} | category: {t.category or 'N/A'} | {t.name}: {t.value} | canon: {t.canon_status or 'N/A'} | ref: {t.reference or 'N/A'} | confidence: {t.confidence or 'N/A'}"
            for t in traits
        ])

async def tool_save_unconfirmed_trait(args: Dict[str, Any]) -> str:
    """
    Accepts either a single trait via the top-level name/value/... fields,
    or a batch via `items`: [{name, value, category, canon_status,
    reference, wiki_source, confidence}, ...]. Batching lets the Researcher
    persist everything it found on one page in a single tool call instead of
    one round trip (and one LLM call) per item.
    """
    universe_name = get_current_universe()
    if not universe_name:
        return "Error: No active universe context."

    items = args.get("items")
    if not items:
        single = {
            "name": args.get("name", ""),
            "value": args.get("value", ""),
            "category": args.get("category"),
            "canon_status": args.get("canon_status"),
            "reference": args.get("reference"),
            "wiki_source": args.get("wiki_source"),
            "confidence": args.get("confidence"),
        }
        items = [single]

    saved, errors = [], []
    with Session(unconfirmed_engine) as session:
        universe = session.exec(select(UnconfirmedUniverse).where(UnconfirmedUniverse.name == universe_name)).first()
        if not universe:
            universe = UnconfirmedUniverse(name=universe_name)
            session.add(universe)
            session.flush()

        for item in items:
            trait_name = item.get("name", "")
            if not trait_name:
                errors.append(f"Skipped item with missing name: {item}")
                continue
            session.add(UnconfirmedTrait(
                universe_id=universe.id,
                name=trait_name,
                value=item.get("value", ""),
                category=item.get("category"),
                canon_status=item.get("canon_status"),
                reference=item.get("reference"),
                wiki_source=item.get("wiki_source"),
                confidence=item.get("confidence"),
            ))
            saved.append(trait_name)

        session.commit()

    result = f"Saved {len(saved)} unconfirmed trait(s) for {universe_name}: {', '.join(saved) if saved else 'none'}."
    if errors:
        result += " Errors: " + "; ".join(errors)
    return result

async def tool_delete_unconfirmed_trait(args: Dict[str, Any]) -> str:
    """Accepts either a single `trait_id`, or a batch via `trait_ids`: [id, ...]."""
    trait_ids = args.get("trait_ids")
    if not trait_ids:
        single_id = args.get("trait_id")
        if not single_id:
            return "Error: Missing trait_id or trait_ids."
        trait_ids = [single_id]

    universe_name = get_current_universe()
    if not universe_name:
        return "Error: No active universe context."

    deleted, errors = [], []
    with Session(unconfirmed_engine) as session:
        universe = session.exec(select(UnconfirmedUniverse).where(UnconfirmedUniverse.name == universe_name)).first()
        for trait_id in trait_ids:
            trait = session.get(UnconfirmedTrait, trait_id)
            if not trait:
                errors.append(f"{trait_id} not found")
                continue
            if not universe or trait.universe_id != universe.id:
                errors.append(f"{trait_id} does not belong to current universe")
                continue
            session.delete(trait)
            deleted.append(str(trait_id))
        session.commit()

    result = f"Deleted {len(deleted)} unconfirmed trait(s): {', '.join(deleted) if deleted else 'none'}."
    if errors:
        result += " Errors: " + "; ".join(errors)
    return result


async def tool_save_unconfirmed_claim(args: Dict[str, Any]) -> str:
    """
    Save unconfirmed claims for the active universe. 
    Claims are atomic statements: (subject, predicate, object).
    Prefer batching via `items`: [{subject, predicate, object_val, reference, wiki_source, confidence}, ...].
    """
    universe_name = get_current_universe()
    if not universe_name:
        return "Error: No active universe context."

    items = args.get("items")
    if not items:
        single = {
            "subject": args.get("subject", ""),
            "predicate": args.get("predicate", ""),
            "object_val": args.get("object_val", ""),
            "reference": args.get("reference"),
            "wiki_source": args.get("wiki_source"),
            "confidence": args.get("confidence"),
        }
        items = [single]

    saved, errors = [], []
    with Session(unconfirmed_engine) as session:
        universe = session.exec(select(UnconfirmedUniverse).where(UnconfirmedUniverse.name == universe_name)).first()
        if not universe:
            universe = UnconfirmedUniverse(name=universe_name)
            session.add(universe)
            session.flush()

        for item in items:
            subject = item.get("subject", "")
            predicate = item.get("predicate", "")
            object_val = item.get("object_val", "")
            if not all([subject, predicate, object_val]):
                errors.append(f"Skipped claim with missing required fields: {item}")
                continue
            session.add(UnconfirmedClaim(
                universe_id=universe.id,
                subject=subject,
                predicate=predicate,
                object_val=object_val,
                reference=item.get("reference"),
                wiki_source=item.get("wiki_source"),
                confidence=item.get("confidence"),
            ))
            saved.append(f"({subject}, {predicate}, {object_val})")
        session.commit()

    result = f"Saved {len(saved)} unconfirmed claim(s) for {universe_name}."
    if errors:
        result += " Errors: " + "; ".join(errors)
    return result


async def tool_query_unconfirmed_claims(args: Dict[str, Any]) -> str:
    universe_name = get_current_universe()
    if not universe_name:
        return "Error: No active universe context."

    with Session(unconfirmed_engine) as session:
        universe = session.exec(select(UnconfirmedUniverse).where(UnconfirmedUniverse.name == universe_name)).first()
        if not universe:
            return f"No unconfirmed data for {universe_name}."

        claims = session.exec(
            select(UnconfirmedClaim).where(UnconfirmedClaim.universe_id == universe.id)
        ).all()
        if not claims:
            return f"No unconfirmed claims for {universe_name}."

        return "\n".join([
            f"ID: {c.id} | {c.subject} --{c.predicate}--> {c.object_val} | ref: {c.reference or 'N/A'} | conf: {c.confidence or 'N/A'}"
            for c in claims
        ])


async def tool_delete_unconfirmed_claim(args: Dict[str, Any]) -> str:
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
        universe = session.exec(select(UnconfirmedUniverse).where(UnconfirmedUniverse.name == universe_name)).first()
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


async def tool_query_claims(args: Dict[str, Any]) -> str:
    universe_name = get_current_universe()
    if not universe_name:
        return "Error: No active universe context."

    predicate_filter = args.get("predicate")

    with Session(engine) as session:
        universe = session.exec(select(Universe).where(Universe.name == universe_name)).first()
        if not universe:
            return f"Universe {universe_name} not found."

        query = select(Claim).where(Claim.universe_scope == universe.id)
        if predicate_filter:
            query = query.where(Claim.predicate == predicate_filter)
        
        claims = session.exec(query).all()
        if not claims:
            return f"No verified claims found for {universe_name}."

        return "\n".join([
            f"ID: {c.id} | subj: {c.subject_id} | pred: {c.predicate} | obj: {c.object_entity_id or c.object_literal} | support: {c.support_count}"
            for c in claims
        ])


async def tool_query_unconfirmed_claims(args: Dict[str, Any]) -> str:
    universe_name = get_current_universe()
    if not universe_name:
        return "Error: No active universe context."

    with Session(unconfirmed_engine) as session:
        universe = session.exec(select(UnconfirmedUniverse).where(UnconfirmedUniverse.name == universe_name)).first()
        if not universe:
            return f"No unconfirmed data for {universe_name}."

        claims = session.exec(
            select(UnconfirmedClaim).where(UnconfirmedClaim.universe_id == universe.id)
        ).all()
        if not claims:
            return f"No unconfirmed claims for {universe_name}."

        return "\n".join([
            f"ID: {c.id} | subj: {c.subject} | pred: {c.predicate} | obj: {c.object_val} | ref: {c.reference or 'N/A'} | conf: {c.confidence or 'N/A'}"
            for c in claims
        ])

AGENT_TOOLS: Dict[str, Dict[str, Any]] = {
    "webSearch": {
        "func": tool_web_search,
        "description": "Search the web for lore, technology, or cosmology. Returns up to 10 results. If a result set looks blocked/bot-checked or comes back empty unexpectedly, try a different engine rather than assuming nothing exists.",
        "parameters": {
            "type": "object",
            "properties": {
                "search_query": {"type": "string", "description": "The search query to use."},
                "engine": {"type": "string", "description": "Search engine to use (google, duckduckgo, brave).", "default": "google"},
                "site_filter": {"type": "string", "description": "Restrict search to a specific domain (e.g. 'fandom.com')."}
            },
            "required": ["search_query"]
        }
    },
    "fetchPage": {
        "func": tool_fetch_page,
        "description": "Fetch and read the full text of a specific URL. Reads are cached and count against a shared per-run fetch budget (also shared with compareSourceFreshness). Returns structured content including the main article, a scored list of internal research leads (links), and metadata. You can specify `max_links` to get more or fewer internal links.",
        "parameters": {
            "type": "object",
            "properties": {
                "urls": {"type": "array", "items": {"type": "string"}, "description": "List of URLs to fetch."},
                "url": {"type": "string", "description": "A single URL to fetch."},
                "max_links": {"type": "integer", "description": "Maximum number of internal research links to return. Default is 20.", "default": 20}
            },
            "required": []
        }
    },
    "compareSourceFreshness": {
        "func": tool_compare_source_freshness,
        "description": "Compare 2+ candidate URLs for the same subject and report which is actively maintained vs. stale/moved/archived, using HTTP headers, on-page 'last edited' text, and redirect/canonical signals. Use this whenever webSearch surfaces more than one plausible wiki for the same universe, BEFORE settling on a canonical domain. Shares the same per-run fetch budget/cache as fetchPage — comparing candidates you've already fetched costs nothing extra.",
        "parameters": {
            "type": "object",
            "properties": {
                "urls": {"type": "array", "items": {"type": "string"}, "description": "2 or more candidate URLs covering the same subject/universe."}
            },
            "required": ["urls"]
        }
    },
    "queryTraits": {
        "func": tool_query_universe_traits,
        "description": "Retrieve all current traits for the active universe from the database.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    "upsertTrait": {
        "func": tool_upsert_trait,
        "description": "Create or update trait(s) for the active universe. Prefer batching: pass `items` with all the traits you're about to commit for this world in one call, rather than calling this once per trait.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Single-trait mode: the name of the trait."},
                "value": {"type": "string", "description": "Single-trait mode: the value of the trait."},
                "items": {
                    "type": "array",
                    "description": "Batch mode (preferred): a list of traits to upsert in one call.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "value": {"type": "string"}
                        },
                        "required": ["name", "value"]
                    }
                }
            },
            "required": []
        }
    },
    "upsertClaims": {
        "func": tool_upsert_claims,
        "description": "Integrate atomic claims (Subject, Predicate, Object) into the permanent records. Use this to promote verified findings from the researcher. Prefer batching via `items`.",
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "The entity the claim is about."},
                "predicate": {"type": "string", "description": "The relationship or property (e.g. 'is_a', 'located_in')."},
                "object_val": {"type": "string", "description": "The target entity or value."},
                "source_reference": {"type": "string", "description": "URL and section reference."},
                "source_wiki": {"type": "string", "description": "Wiki page name or URL."},
                "confidence": {"type": "number", "description": "Confidence score (0.0 to 1.0)."},
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
                            "confidence": {"type": "number"}
                        },
                        "required": ["subject", "predicate", "object_val"]
                    }
                }
            },
            "required": []
        }
    },
    "queryUnconfirmedTraits": {
        "func": tool_query_unconfirmed_traits,
        "description": "Retrieve all unconfirmed traits for the active universe from the database.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    "queryClaims": {
        "func": tool_query_claims,
        "description": "Query verified claims from the main database for the current universe. Optionally filter by a specific predicate.",
        "parameters": {
            "type": "object",
            "properties": {
                "predicate": {"type": "string", "description": "The predicate to filter by."}
            },
            "required": []
        }
    },
    "queryUnconfirmedClaims": {
        "func": tool_query_unconfirmed_claims,
        "description": "Retrieve all unconfirmed atomic claims (S-P-O) for the active universe.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    "saveUnconfirmedTrait": {
        "func": tool_save_unconfirmed_trait,
        "description": "Save unconfirmed trait(s) for the active universe. Prefer batching: when you've gathered several findings from the same page/session, pass them all via `items` in one call rather than calling this once per finding.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Single-item mode: the name of the trait."},
                "value": {"type": "string", "description": "Single-item mode: the value of the trait."},
                "category": {"type": "string", "description": "Single-item mode: category (Cosmology, Hard Tech, Magic System, etc.)."},
                "canon_status": {"type": "string", "description": "Single-item mode: canon status (Verified, Unverified, Fanon, Unclear)."},
                "reference": {"type": "string", "description": "Single-item mode: URL and section reference."},
                "wiki_source": {"type": "string", "description": "Single-item mode: wiki page name or URL."},
                "confidence": {"type": "string", "description": "Single-item mode: confidence level (high, medium, low)."},
                "items": {
                    "type": "array",
                    "description": "Batch mode (preferred): a list of findings to save in one call.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "value": {"type": "string"},
                            "category": {"type": "string"},
                            "canon_status": {"type": "string"},
                            "reference": {"type": "string"},
                            "wiki_source": {"type": "string"},
                            "confidence": {"type": "string"}
                        },
                        "required": ["name", "value"]
                    }
                }
            },
            "required": []
        }
    },
    "saveUnconfirmedClaim": {
        "func": tool_save_unconfirmed_claim,
        "description": "Save unconfirmed atomic claims (S-P-O) for the active universe. This is the primary way to persist granular knowledge. Prefer batching via `items`.",
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "The entity the claim is about."},
                "predicate": {"type": "string", "description": "The relationship or property (e.g. 'is_a', 'located_in', 'has_power')."},
                "object_val": {"type": "string", "description": "The value or target entity of the claim."},
                "reference": {"type": "string", "description": "URL and section reference."},
                "wiki_source": {"type": "string", "description": "Wiki page name or URL."},
                "confidence": {"type": "string", "description": "Confidence level (high, medium, low)."},
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
                            "confidence": {"type": "string"}
                        },
                        "required": ["subject", "predicate", "object_val"]
                    }
                }
            },
            "required": []
        }
    },
    "deleteUnconfirmedTrait": {
        "func": tool_delete_unconfirmed_trait,
        "description": "Delete unconfirmed trait(s) by ID for the active universe. Prefer batching: pass `trait_ids` with every ID you're removing in one call rather than calling this once per ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "trait_id": {"type": "integer", "description": "Single-item mode: the ID of the unconfirmed trait to delete."},
                "trait_ids": {"type": "array", "items": {"type": "integer"}, "description": "Batch mode (preferred): all IDs to delete in one call."}
            },
            "required": []
        }
    },
    "deleteUnconfirmedClaim": {
        "func": tool_delete_unconfirmed_claim,
        "description": "Delete unconfirmed claim(s) by ID for the active universe.",
        "parameters": {
            "type": "object",
            "properties": {
                "claim_id": {"type": "integer", "description": "Single-item mode: the ID of the unconfirmed claim to delete."},
                "claim_ids": {"type": "array", "items": {"type": "integer"}, "description": "Batch mode (preferred): all IDs to delete in one call."}
            },
            "required": []
        }
    },
}
