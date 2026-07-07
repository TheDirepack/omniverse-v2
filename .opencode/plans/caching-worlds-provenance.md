# Knowledge Pipeline: Caching, Worlds & Provenance

## Overview

Addresses criticism about caching architecture, world model, acquisition pipeline, provenance/observability, and UI gaps. Organized in dependency order — each phase unlocks the next.

---

## Phase 1: World Model Enhancement

**Goal**: Give worlds immutable IDs and rich metadata so caching and provenance don't break on rename. Replace bare-name world creation with a registry-aware import flow.

### Why first
- Caching artifacts must be keyed by content hash, not world name — but artifacts still need to reference which worlds used them. If worlds can be renamed, the reference breaks unless there's a stable UUID.
- Cross-world cache sharing (same wiki page used by two overlapping worlds) requires knowing which worlds share a franchise/continuity — metadata must exist.
- The current `POST /api/worlds {name}` creates orphans with no metadata, making cache dedup impossible.

### Changes

| File | Action | What |
|---|---|---|
| `db/schema.py:Universe` | Add `uuid` column | `uuid: str = Field(default_factory=lambda: str(uuid4()), index=True, unique=True)` — stable identifier independent of slug/name. Existing rows backfilled on DB init. |
| `db/unconfirmed_schema.py:UnconfirmedUniverse` | Add `universe_uuid` | Mirror the UUID so unconfirmed notes can reference the stable ID even before promotion. |
| `services/universe_service.py` | Add `get_universe_by_uuid()`, `import_from_registry()` | `import_from_registry(world_id)` reads `default_worlds.json`, creates Universe with all metadata (franchise, continuity, era, parent_id, category). Returns existing if already imported. |
| `api/routers/worlds.py` | Split `POST /worlds` into two | `POST /worlds/import {world_id}` — import from registry. `POST /worlds/create {name, franchise, continuity, era, parent_id, category}` — create custom with full metadata. Keep legacy `POST /worlds {name}` deprecated but working (auto-detects if name matches registry). |
| `services/universe_service.py` | `create_universe()` | Accept optional metadata params instead of just name. |
| `db/default_worlds.json` | Verify format | Already has `id`, `name`, `franchise`, `category`, `continuity`, `era` — just ensure it has a unique `id` per entry. |

### Data flow
```
Import World:  POST /worlds/import {world_id: "battletech"}
  -> UniverseService.import_from_registry("battletech")
  -> reads default_worlds.json, finds entry
  -> creates Universe(uuid=uuid4(), slug="battletech", name="BattleTech", franchise="BattleTech", ...)
  -> returns {uuid, slug, name, ...}

Create Custom: POST /worlds/create {name, franchise, continuity, era}
  -> UniverseService.create_universe(name, franchise, continuity, era, category)
  -> creates Universe(uuid=uuid4(), slug=slugify(name), ...)
  -> returns {uuid, slug, name, ...}
```

---

## Phase 2: Acquisition Cache (Three-Layer System)

**Goal**: Formalize three distinct layers — Acquisition Cache (world-agnostic, content-hash keyed), Research Notes (world-scoped observations derived from acquisition), Main DB (validated canonical claims).

### Current state vs target

| Layer | Current | Target |
|---|---|---|
| Acquisition Cache | In-memory `dict[str,str]` by URL, lost on error | Persistent in `unconfirmed.db`, keyed by SHA-256, versioned, single-flight |
| Research Notes | `UnconfirmedClaim` + `UnconfirmedUniverse` mixed together | Same tables but clearly scoped to a world+run, with FK back to `AcquisitionArtifact` |
| Main DB | `Claim` table, no source link | `Claim` with FK to `AcquisitionArtifact` via provenance edges |

### Cache architecture

```
┌─────────────────────────────────────────────┐
│           AcquisitionCache class            │
│  ┌───────────────────┐  ┌────────────────┐  │
│  │ In-Memory LRU     │  │ Single-Flight  │  │
│  │ (dict, max 500)   │  │ (asyncio.Cond) │  │
│  └────────┬──────────┘  └───────┬────────┘  │
│           │                     │            │
│  ┌────────▼─────────────────────▼────────┐  │
│  │      AcquisitionCacheRepository      │  │
│  │  (persistent in unconfirmed.db)      │  │
│  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

### Tables in `unconfirmed_schema.py`

**`AcquisitionArtifact`** — world-agnostic, keyed by content hash
| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `content_hash` | str | SHA-256 hex, indexed |
| `source_url` | str | original URL |
| `content_type` | str | `search_result`, `web_page`, `pdf`, `ocr` |
| `raw_bytes` | LargeBinary | compressed original bytes |
| `extracted_text` | str | parsed text content |
| `structured_data` | JSON | metadata (links, headings, tables, scores) |
| `engine_name` | str | `trafilatura`, `duckduckgo`, `paddleocr` |
| `engine_version` | str | semver of engine |
| `fetch_duration_ms` | int | |
| `created_at` | datetime | |

**`WorldAcquisitionUsage`** — which worlds used which artifacts (many-to-many)
| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `artifact_id` | int FK -> AcquisitionArtifact | |
| `universe_uuid` | str | stable world ID |
| `run_id` | str | research run that triggered the fetch |
| `usage_type` | str | `direct_fetch`, `search_result`, `cross_world_shared` |
| `created_at` | datetime | |

### Files

| File | Action | What |
|---|---|---|
| `db/unconfirmed_schema.py` | Add 2 tables | `AcquisitionArtifact`, `WorldAcquisitionUsage`. |
| `db/unconfirmed_session.py` | Add to init | Add new tables to `init_unconfirmed_db()`. |
| `repositories/acquisition_cache.py` | **New** | `AcquisitionCacheRepository` — `get_by_hash(hash)`, `get_by_url(url, limit=1)`, `store(artifact)`, `record_usage(artifact_id, universe_uuid, run_id)`, `get_usages(artifact_id)`. |
| `core/acquisition_cache.py` | **New** | `AcquisitionCache` — wraps repo + `dict[str, str]` LRU. `get(key, policy)` with single-flight. `FreshnessPolicy` enum: `CACHE_ONLY`, `PREFER_CACHE`, `FORCE_REFRESH`. Single-flight via `_pending: dict[str, asyncio.Future]` — second caller awaits first's future. |
| `core/web_fetch.py` | `fetch_page()` return sig | Return `(text, content_hash, structured_metadata)` tuple. |
| `core/web_search.py` | `perform_search()` return sig | Return `(results_json, content_hash, search_metadata)`. |
| `core/tools.py` | Update `tool_fetch_page`/`tool_web_search` | After fetch/search, store result in `AcquisitionCache`. Record `WorldAcquisitionUsage` linking current world + run to the artifact. |
| `core/agent_engine.py` | Replace `FetchCache` | `_read_page_with_budget` delegates to global `AcquisitionCache` instance. Remove `run_fetch_cache` singleton, `FetchCache` class. |
| `core/agent_engine.py` | Add `acquisition_cache` param | `run_agent()` accepts optional `AcquisitionCache`; falls back to global singleton. |
| `research/researcher.py` | Wire in | Pass global `AcquisitionCache` to `run_agent()` calls. |
| `research/researcher.py` | `research_single_world()` | After researcher completes, clear per-run in-memory cache but persistent cache remains. |

### Single-flight logic (pseudocode)

```python
async def get(self, url: str, policy: FreshnessPolicy) -> ArtifactResult | None:
    # Check in-memory LRU first
    if url in self._lru:
        return self._lru[url]

    # Check persistent cache
    artifact = await self.repo.get_by_url(url)
    if artifact and policy != FORCE_REFRESH:
        self._lru[url] = artifact
        return artifact

    # Single-flight: dedup concurrent fetches for same URL
    if url in self._pending:
        return await self._pending[url]  # await existing fetch

    future = asyncio.get_event_loop().create_future()
    self._pending[url] = future
    try:
        result = await self._do_fetch(url)
        future.set_result(result)
        return result
    except Exception as e:
        future.set_exception(e)
        raise
    finally:
        self._pending.pop(url, None)
```

---

## Phase 3: Worlds UI

**Goal**: Replace the flat name-in-a-box world UX with dedicated screens for importing, creating, browsing hierarchy, and viewing relationships.

### New/Dedicated Screens

**`/worlds`** — World Management hub
- Tab 1: **Import World** — search `default_worlds.json`, preview metadata, import button
- Tab 2: **Create Custom** — form with Name, Franchise, Continuity, Era, Parent World (dropdown of existing), Category
- Tab 3: **World Graph** — hierarchical tree with collapsible branches showing parent/child/continuity links. Click world opens detail.

**Changes to existing pages:**

| Page | Change |
|---|---|
| `research.html` "Add New World" form | Replace single name input with two-button choice: "Import from Registry" (opens `/worlds` import tab) or "Create Custom" (opens `/worlds` create tab). Keep quick name input that auto-detects registry match. |
| `knowledge.html` world tree | Expand each world row to show parent, franchise, continuity tags. Add "View Neighborhood" button that loads related worlds (parent/children/same franchise/same continuity). |

### Files

| File | Action | What |
|---|---|---|
| `views/worlds.py` | **New view router** | `GET /worlds/` — worlds hub page. `GET /worlds/import` — fragment listing registry entries with search. `POST /worlds/import/{world_id}` — import from registry, render updated list. `GET /worlds/create` — fragment with creation form. `POST /worlds/create` — create custom, render updated list. `GET /worlds/graph` — hierarchy tree fragment. `GET /worlds/{uuid}/neighborhood` — related worlds fragment. |
| `templates/pages/worlds.html` | **New** | Worlds hub with 3 tabs (Import, Create, Graph). |
| `templates/fragments/world_import_list.html` | **New** | Registry search results with import button. |
| `templates/fragments/world_create_form.html` | **New** | Custom world creation form. |
| `templates/fragments/world_hierarchy.html` | **New** | Recursive hierarchy tree (similar to `world_row.html` but with relationship labels). |
| `templates/fragments/world_neighborhood.html` | **New** | Related worlds card list. |
| `templates/pages/research.html` | Update "Add New World" | Replace current form with smart "Import / Create" flow. |
| `templates/fragments/world_row.html` | Update | Add parent/franchise/continuity badges, "Neighborhood" action. |
| `main.py` | Register | `app.include_router(worlds_views_router, prefix="/worlds")` |
| `base.html` | Nav link | Add "Worlds" to nav. |

---

## Phase 4: Provenance / Observability

**Goal**: Every claim traceable end-to-end: source URL -> acquisition artifact -> research notes -> validation -> claim in Main DB.

### Data model

`ProvenanceEdge` table in `unconfirmed_schema.py`:

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `source_artifact_id` | int FK -> AcquisitionArtifact | the acquisition step |
| `target_type` | str | `unconfirmed_claim`, `main_claim`, `search_result` |
| `target_id` | int | PK of the target row |
| `relation` | str | `extracted_from`, `derived_from`, `referenced_by` |
| `run_id` | str | the research run that created this link |
| `created_at` | datetime | |

### Files

| File | Action | What |
|---|---|---|
| `db/unconfirmed_schema.py` | Add table | `ProvenanceEdge`. |
| `core/tools.py` | `tool_save_unconfirmed_claim()` | After save, create `ProvenanceEdge` linking the latest `AcquisitionArtifact` for this world to the new claim. |
| `core/tools.py` | `tool_upsert_claims()` | After upsert to Main DB, create `ProvenanceEdge` linking `AcquisitionArtifact` -> Main DB Claim. |
| `core/agent_engine.py` | Track current artifact | Set `current_artifact_id` in `ContextVar` before `_execute_tool` so downstream tools can link back. |
| `views/provenance.py` | **New view router** | `GET /provenance/claim/{claim_id}` — full trace backwards. `GET /provenance/artifact/{artifact_id}` — artifact detail + all derived claims. |
| `templates/pages/provenance.html` | **New** | Provenance trace page with vertical timeline. |
| `templates/fragments/provenance_trace.html` | **New** | HTMX expandable trace steps. |
| `templates/fragments/entity_detail.html` | Update | Add "View Provenance" link per claim. |
| `views/knowledge.py` | Update | Link entity detail to provenance. |

### Trace flow (example)
```
Claim "K2 is 750m tall" in Main DB
  └─ ProvenanceEdge: target_type=main_claim, target_id=42, relation=extracted_from
      └─ AcquisitionArtifact id=7 (SHA-256: abc123, source=wikipedia.org/K2)
          └─ ProvenanceEdge: target_type=unconfirmed_claim, target_id=99
              └─ UnconfirmedClaim id=99 (subject=K2, predicate=height, object=750m)
                  └─ ProvenanceEdge: target_type=acquisition_artifact, target_id=3
                      └─ AcquisitionArtifact id=3 (search result for "K2 height")
```

---

## Phase 5: Validation & Search Scope

**Goal**: Make validation aware of duplicate worlds. Allow research scoped by world relationship.

### Duplicate world handling

| File | Action | What |
|---|---|---|
| `views/validation.py` | Add duplicates section | Query `UnconfirmedUniverse` for name-similar matches against Main DB `Universe`. Show side-by-side with merge/keep-both action. |
| `templates/pages/validation.html` | Add "Duplicate Worlds" tab | New tab showing potential duplicates with approve/reject/merge buttons. |
| `templates/fragments/duplicate_world_card.html` | **New** | Side-by-side comparison of two potential duplicate worlds with merge action. |
| `services/universe_service.py` | `find_duplicates(name)` | Fuzzy name match across Main DB, return candidates with similarity score. `merge_worlds(keep_id, merge_id)` — merge claims/entities from merge_id into keep_id, delete merge_id. |

### Search scope by relationship

| File | Action | What |
|---|---|---|
| `api/routers/worlds.py` | `POST /worlds/{uuid}/research` | Accept scope param: `this_world_only`, `continuity`, `franchise`, `neighborhood`. Expand target worlds list accordingly before launching research. |
| `views/research.py` | Update research page | Add scope selector when researching existing world (dropdown: "This world only" / "Entire continuity" / "Same franchise"). |
| `templates/fragments/database_worlds.html` | Update | Add scope selector to "Research" button, expand into dropdown. |

---

## File Manifest

### New files (17)
1. `repositories/acquisition_cache.py`
2. `core/acquisition_cache.py`
3. `views/worlds.py` (view router)
4. `views/provenance.py` (view router)
5. `templates/pages/worlds.html`
6. `templates/pages/provenance.html`
7. `templates/fragments/world_import_list.html`
8. `templates/fragments/world_create_form.html`
9. `templates/fragments/world_hierarchy.html`
10. `templates/fragments/world_neighborhood.html`
11. `templates/fragments/provenance_trace.html`
12. `templates/fragments/duplicate_world_card.html`

### Modified files (17)
1. `db/schema.py` — add `Universe.uuid`
2. `db/unconfirmed_schema.py` — add 3 tables (`AcquisitionArtifact`, `WorldAcquisitionUsage`, `ProvenanceEdge`)
3. `db/unconfirmed_session.py` — init new tables
4. `services/universe_service.py` — uuid support, import_from_registry, find_duplicates, merge_worlds
5. `api/routers/worlds.py` — split POST /worlds, add import/create
6. `core/web_fetch.py` — return content_hash
7. `core/web_search.py` — return content_hash
8. `core/tools.py` — wire cache + provenance
9. `core/agent_engine.py` — replace FetchCache, track artifact context
10. `research/researcher.py` — wire global AcquisitionCache
11. `views/research.py` — scope selector, improved add-world
12. `views/validation.py` — duplicate worlds section
13. `views/knowledge.py` — provenance links
14. `templates/pages/research.html` — smart add-world flow
15. `templates/pages/validation.html` — duplicate worlds tab
16. `templates/fragments/world_row.html` — rich badges
17. `templates/fragments/entity_detail.html` — provenance links
18. `main.py` — register new view routers
19. `base.html` — nav links

**Total: ~36 files, 17 new**

---

## Dependency order

```
Phase 1 (World Model) ──► Phase 2 (Cache) ──► Phase 4 (Provenance)
       │                                              │
       ▼                                              │
Phase 3 (Worlds UI) ──────────────────────────────────┘
       │
       ▼
Phase 5 (Validation + Scope)
```

Phase 3 (Worlds UI) can start in parallel with Phase 2 since it mostly touches different files (views/templates vs core/db). Phase 4 depends on Phase 2's artifact model. Phase 5 depends on Phase 1's world model + Phase 3's UI.
