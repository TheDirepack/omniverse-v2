from typing import Any, Dict, List, Optional
from sqlmodel import Session, select
from app.db.session import engine
from app.db.schema import Universe, Trait
from app.db.unconfirmed_session import engine as unconfirmed_engine
from app.db.unconfirmed_schema import UnconfirmedUniverse, UnconfirmedTrait
from app.core.web_search import web_searcher
from app.core.web_fetch import web_fetcher
from app.core.context import get_current_universe

async def tool_web_search(args: Dict[str, Any]) -> str:
    query = args.get("search_query", "")
    if not query:
        return "Error: Missing search_query argument."
    engine = args.get("engine", "google")
    site_filter = args.get("site_filter", None)
    return await web_searcher.perform_search(query, engine=engine, site_filter=site_filter)

async def tool_fetch_page(args: Dict[str, Any]) -> str:
    urls = args.get("urls", [])
    if not urls or not isinstance(urls, list):
        if isinstance(urls, str):
            urls = [urls]
        else:
            return "Error: Missing or invalid urls argument (expected list)."

    results = []
    for url in urls:
        try:
            content = await web_fetcher.fetch_page(url)
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
        "description": "Fetch and read the full text of a specific URL. Reads are cached and count against a shared per-run fetch budget (also shared with compareSourceFreshness), so re-fetching the same URL is free but the total number of distinct pages you can read in one research pass is limited — spend it on pages you actually need.",
        "parameters": {
            "type": "object",
            "properties": {
                "urls": {"type": "array", "items": {"type": "string"}, "description": "List of URLs to fetch."},
                "url": {"type": "string", "description": "A single URL to fetch."}
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
    "queryUnconfirmedTraits": {
        "func": tool_query_unconfirmed_traits,
        "description": "Retrieve all unconfirmed traits for the active universe from the database.",
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
}
