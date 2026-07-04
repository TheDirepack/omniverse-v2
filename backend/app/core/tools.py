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
    universe_name = get_current_universe()
    trait_name = args.get("name", "")
    trait_value = args.get("value", "")

    if not universe_name:
        return "Error: No active universe context."
    if not trait_name:
        return "Error: Missing trait name."

    with Session(engine) as session:
        universe = session.exec(select(Universe).where(Universe.name == universe_name)).first()
        if not universe:
            return f"Universe {universe_name} not found."

        trait = session.exec(select(Trait).where(Trait.universe_id == universe.id, Trait.name == trait_name)).first()
        if trait:
            trait.value = trait_value
            msg = "Updated existing trait."
        else:
            session.add(Trait(universe_id=universe.id, name=trait_name, value=trait_value))
            msg = "Created new trait."

        session.commit()
        return f"Successfully {msg} for {universe_name}: {trait_name}"

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
    universe_name = get_current_universe()
    trait_name = args.get("name", "")
    trait_value = args.get("value", "")
    category = args.get("category")
    canon_status = args.get("canon_status")
    reference = args.get("reference")
    wiki_source = args.get("wiki_source")
    confidence = args.get("confidence")

    if not universe_name:
        return "Error: No active universe context."
    if not trait_name:
        return "Error: Missing trait name."

    with Session(unconfirmed_engine) as session:
        universe = session.exec(select(UnconfirmedUniverse).where(UnconfirmedUniverse.name == universe_name)).first()
        if not universe:
            universe = UnconfirmedUniverse(name=universe_name)
            session.add(universe)
            session.flush()

        session.add(UnconfirmedTrait(
            universe_id=universe.id,
            name=trait_name,
            value=trait_value,
            category=category,
            canon_status=canon_status,
            reference=reference,
            wiki_source=wiki_source,
            confidence=confidence,
        ))
        session.commit()
        return f"Saved unconfirmed trait '{trait_name}' for {universe_name}."

async def tool_delete_unconfirmed_trait(args: Dict[str, Any]) -> str:
    trait_id = args.get("trait_id")
    if not trait_id:
        return "Error: Missing trait_id."

    with Session(unconfirmed_engine) as session:
        trait = session.get(UnconfirmedTrait, trait_id)
        if not trait:
            return f"UnconfirmedTrait {trait_id} not found."

        universe_name = get_current_universe()
        if not universe_name:
            return "Error: No active universe context."

        universe = session.exec(select(UnconfirmedUniverse).where(UnconfirmedUniverse.name == universe_name)).first()
        if not universe or trait.universe_id != universe.id:
            return f"Trait {trait_id} does not belong to current universe."

        session.delete(trait)
        session.commit()
        return f"Deleted unconfirmed trait {trait_id}."

AGENT_TOOLS: Dict[str, Dict[str, Any]] = {
    "webSearch": {
        "func": tool_web_search,
        "description": "Search the web for lore, technology, or cosmology.",
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
        "description": "Fetch and read the full text of a specific URL.",
        "parameters": {
            "type": "object",
            "properties": {
                "urls": {"type": "array", "items": {"type": "string"}, "description": "List of URLs to fetch."},
                "url": {"type": "string", "description": "A single URL to fetch."}
            },
            "required": []
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
        "description": "Create or update a specific trait for the active universe.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The name of the trait."},
                "value": {"type": "string", "description": "The value of the trait."}
            },
            "required": ["name", "value"]
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
        "description": "Save a new unconfirmed trait for the active universe.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The name of the trait."},
                "value": {"type": "string", "description": "The value of the trait."},
                "category": {"type": "string", "description": "Category (Cosmology, Hard Tech, Magic System, etc.)."},
                "canon_status": {"type": "string", "description": "Canon status (Verified, Unverified, Fanon, Unclear)."},
                "reference": {"type": "string", "description": "URL and section reference."},
                "wiki_source": {"type": "string", "description": "Wiki page name or URL."},
                "confidence": {"type": "string", "description": "Confidence level (high, medium, low)."}
            },
            "required": ["name", "value"]
        }
    },
    "deleteUnconfirmedTrait": {
        "func": tool_delete_unconfirmed_trait,
        "description": "Delete an unconfirmed trait by ID for the active universe.",
        "parameters": {
            "type": "object",
            "properties": {
                "trait_id": {"type": "integer", "description": "The ID of the unconfirmed trait to delete."}
            },
            "required": ["trait_id"]
        }
    },
}
