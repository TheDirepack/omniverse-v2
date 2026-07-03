import asyncio
from typing import Any, Dict, Callable, List
from sqlmodel import Session, select
from app.db.session import engine
from app.db.schema import Universe, Trait
from app.core.web_search import web_searcher
from app.core.web_fetch import web_fetcher

async def tool_web_search(args: Dict[str, Any]) -> str:
    query = args.get("search_query", "")
    if not query:
        return "Error: Missing search_query argument."
    return await web_searcher.perform_search(query)

async def tool_fetch_page(args: Dict[str, Any]) -> str:
    urls = args.get("urls", [])
    if not urls or not isinstance(urls, list):
        # Handle single URL string case
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
    universe_name = args.get("universe_name", "")
    if not universe_name:
        return "Error: Missing universe_name."
    
    with Session(engine) as session:
        universe = session.exec(select(Universe).where(Universe.name == universe_name)).first()
        if not universe:
            return f"Universe {universe_name} not found."
        
        traits = session.exec(select(Trait).where(Trait.universe_id == universe.id)).all()
        if not traits:
            return f"No traits currently found for {universe_name}."
        
        return "\n".join([f"ID: {t.id} | {t.name}: {t.value}" for t in traits])

async def tool_upsert_trait(args: Dict[str, Any]) -> str:
    universe_name = args.get("universe_name", "")
    trait_name = args.get("name", "")
    trait_value = args.get("value", "")
    
    if not universe_name or not trait_name:
        return "Error: Missing universe_name or trait name."
    
    with Session(engine) as session:
        universe = session.exec(select(Universe).where(Universe.name == universe_name)).first()
        if not universe:
            return f"Universe {universe_name} not found."
        
        # Check if trait already exists
        trait = session.exec(select(Trait).where(Trait.universe_id == universe.id, Trait.name == trait_name)).first()
        if trait:
            trait.value = trait_value
            msg = "Updated existing trait."
        else:
            session.add(Trait(universe_id=universe.id, name=trait_name, value=trait_value))
            msg = "Created new trait."
        
        session.commit()
        return f"Successfully {msg} for {universe_name}: {trait_name}"

async def tool_update_universe_meta(args: Dict[str, Any]) -> str:
    universe_name = args.get("universe_name", "")
    raw_data = args.get("raw_data")
    is_explored = args.get("is_explored", None)
    
    if not universe_name:
        return "Error: Missing universe_name."
        
    with Session(engine) as session:
        universe = session.exec(select(Universe).where(Universe.name == universe_name)).first()
        if not universe:
            return f"Universe {universe_name} not found."
        
        if raw_data is not None:
            universe.raw_data = raw_data
        if is_explored is not None:
            universe.is_explored = is_explored
            
        session.add(universe)
        session.commit()
        return f"Updated meta for {universe_name}."

# Registry of available tools
AGENT_TOOLS: Dict[str, Dict[str, Any]] = {
    "webSearch": {
        "func": tool_web_search,
        "description": "Search the web for lore, technology, or cosmology. Arg: { 'search_query': 'string' }."
    },
    "fetchPage": {
        "func": tool_fetch_page,
        "description": "Fetch and read the full text of a specific URL. Arg: { 'urls': ['url1', 'url2'] } or { 'url': 'string' }."
    },
    "queryTraits": {
        "func": tool_query_universe_traits,
        "description": "Retrieve all current traits for a universe from the database. Arg: { 'universe_name': 'string' }."
    },
    "upsertTrait": {
        "func": tool_upsert_trait,
        "description": "Create or update a specific trait for a universe. Arg: { 'universe_name': 'string', 'name': 'string', 'value': 'string' }."
    },
    "updateUniverseMeta": {
        "func": tool_update_universe_meta,
        "description": "Update universe metadata (raw_data, is_explored). Arg: { 'universe_name': 'string', 'raw_data': 'string', 'is_explored': boolean }."
    }
}


