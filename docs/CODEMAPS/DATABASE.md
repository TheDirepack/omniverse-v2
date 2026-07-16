# Omniverse V2 Database Codemap

**Last Updated:** 2026-07-11

## Database Topology

Omniverse V2 uses **multiple isolated SQLite databases** to prevent contamination between canonical knowledge, speculative reasoning, and operational state.

### Database Files

| Database | Filename | Purpose | Location |
| :--- | :--- | :--- | :--- |
| **Main DB** | `omniverse_v2.db` | Canonical Knowledge Graph | `backend/data/` |
| **Settings DB** | `settings.db` | System & Agent Configuration | `backend/data/` |
| **Operational DB** | `operational.db` | Execution logs & state | `backend/data/` |
| **Staging DB** | `notebook.db` | Research workspace | `backend/data/` |
| **Extrapolation DB** | `extrapolation.db` | Speculative theories | `backend/data/` |
| **Acquisition DB** | `acquisition.db` | Web artifacts cache | `backend/data/` |

---

## Main Knowledge Graph Schema

The **Main DB** stores the polymorphic Knowledge Graph - the core of the system.

### Core Entities

#### 1. **Universe** (Root Entity)

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INT | Primary key |
| `uuid` | TEXT | Unique identifier (indexed) |
| `slug` | TEXT | URL-friendly slug (unique) |
| `name` | TEXT | Display name (indexed) |
| `franchise` | TEXT | Franchise/series name |
| `category` | TEXT | Genre/category |
| `continuity` | TEXT | Continuity descriptor |
| `era` | TEXT | Era/time period |
| `parent_id` | INT | Self-referential for hierarchies |
| `summary` | TEXT | Polished summary |
| `raw_data` | TEXT | Raw research data |
| `is_explored` | BOOL | Exploration flag |

**Key Properties**:
- Supports hierarchical universe structures (e.g., "DC Universe" → "Marvel Universe")
- `display_name` property: Returns franchise name if matches era/continuity

---

#### 2. **Artifact** (Polymorphic Knowledge Unit)

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INT | Primary key |
| `universe_id` | INT | FK to Universe (indexed) |
| `type` | TEXT | Entity, Claim, Specification, or Event (indexed) |
| `name` | TEXT | Artifact name (indexed) |
| `confidence` | TEXT | Derived confidence level |
| `freshness` | TEXT | Data freshness indicator |
| `verification_status` | TEXT | PENDING/VERIFIED/etc |
| `evidence_refs` | TEXT | JSON array of evidence IDs (indexed) |
| `support_count` | INT | Number of unique evidence sources (indexed) |
| `source_reference` | TEXT | Source URL |
| `source_wiki` | TEXT | Wiki source reference |
| `payload_json` | TEXT | Structured data (type-specific) |
| `created_at` | DATETIME | Timestamp |
| `updated_at` | DATETIME | Timestamp |

**Key Properties**:
- Polymorphic `payload_json` contains type-specific data
- `support_count` derived from unique `evidence_refs`
- Confidence calculated from support count

---

#### 3. **ArtifactRelation** (Directed Edges)

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INT | Primary key |
| `universe_id` | INT | FK to Universe |
| `from_artifact_id` | INT | FK to Artifact |
| `to_artifact_id` | INT | FK to Artifact |
| `relation_type` | TEXT | Edge type (e.g., POWERED_BY) (indexed) |
| `description` | TEXT | Human-readable description |
| `created_at` | DATETIME | Timestamp |

**Key Properties**:
- Directed edges (from → to)
- Common types: `POWERED_BY`, `PART_OF`, `HAS`, `USES`
- `PredicateService` normalizes raw predicates to canonical forms

---

#### 4. **Evidence** (Knowledge Grounding)

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INT | Primary key |
| `universe_id` | INT | FK to Universe |
| `source_url` | TEXT | Source URL (indexed) |
| `section` | TEXT | Specific section/paragraph (indexed) |
| `source_name` | TEXT | Source name/title |
| `created_at` | DATETIME | Timestamp |

**Constraints**:
- Unique constraint: `(universe_id, source_url, section)`

---

#### 5. **EvidenceChunk** (Content Segments)

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INT | Primary key |
| `evidence_id` | INT | FK to Evidence |
| `content` | TEXT | Chunked content |
| `chunk_index` | INT | Chunk order |
| `created_at` | DATETIME | Timestamp |

**Purpose**: Split evidence content for LLM window management

---

#### 6. **ArtifactVersion** (History)

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INT | Primary key |
| `artifact_id` | INT | FK to Artifact |
| `version` | INT | Version number (indexed) |
| `payload_json` | TEXT | Snapshot of payload |
| `evidence_refs` | TEXT | Evidence refs at version time |
| `created_at` | DATETIME | Timestamp |

**Purpose**: Full historical traceability of knowledge evolution

---

#### 7. **ArtifactType** (Type System)

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INT | Primary key |
| `universe_id` | INT | FK to Universe |
| `type_name` | TEXT | Artifact type |
| `payload_json` | TEXT | Type-specific schema |

---

### Tiering System Tables

#### 8. **TierSystem** (Rubric Definitions)

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INT | Primary key |
| `system_definition` | TEXT | Rubric/schema JSON |
| `version` | INT | Version number |
| `is_active` | BOOL | Active flag |
| `parent_id` | INT | Self-referential for hierarchies |
| `amendment_reason` | TEXT | Why this amendment was made |
| `created_at` | DATETIME | Timestamp |

#### 9. **WorldTier** (Assignments)

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INT | Primary key |
| `universe_id` | INT | FK to Universe |
| `system_id` | INT | FK to TierSystem |
| `tier_number` | INT | Assigned tier |
| `justification` | TEXT | Tiering rationale |

**Constraints**: Unique constraint on `universe_id` (one tier per universe)

#### 10. **Anomaly** (Deviation Records)

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INT | Primary key |
| `universe_id` | INT | FK to Universe |
| `description` | TEXT | What doesn't fit the rubric |
| `detected_at` | DATETIME | Detection timestamp |

**Purpose**: Track universes that don't fit current tiering rubric

---

### Universe Relations

#### 11. **UniverseRelation** (Inter-Universe Links)

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INT | Primary key |
| `from_universe_id` | INT | FK to Universe |
| `to_universe_id` | INT | FK to Universe |
| `relation_type` | TEXT | Relation type (indexed) |
| `description` | TEXT | Human-readable description |
| `created_at` | DATETIME | Timestamp |

**Constraints**: Unique constraint on `(from_universe_id, to_universe_id, relation_type)`

---

## Settings DB Schema

| Table | Purpose | Key Columns |
| :--- | :--- | :--- |
| **Setting** | Key-value store | `key` (PK), `value` |
| **ProviderConfig** | LLM provider configs | `id` (PK), `name`, `provider_type`, `base_url`, `models` |
| **ProviderKey** | API keys | `id` (PK), `provider_id` (FK), `api_key`, `priority` |
| **AgentRouteFallback** | Agent routing | `id` (PK), `task_type`, `priority`, `provider_id` (FK), `models` |

---

## Operational DB Schema

| Table | Purpose | Key Columns |
| :--- | :--- | :--- |
| **ExecutionState** | Run tracking | `id` (PK), `run_id`, `node_name`, `thought`, `status`, `state_snapshot`, `duration_ms`, `token_usage`, `cost` |
| **CandidateHealth** | Provider health | `candidate_hash` (PK), `provider_id`, `key_id`, `model`, `failure_count`, `last_failure_at`, `disabled_until` |

---

## Staging DB Schema (Notebook)

| Table | Purpose | Key Columns |
| :--- | :--- | :--- |
| **NotebookUniverse** | Research universes | `uuid` (PK), `name`, `franchise`, `is_explored` |
| **NotebookEntry** | Research notes | `id` (PK), `universe_uuid` (FK), `title`, `summary`, `kind`, `details`, `status`, `priority` |
| **Source** | Research sources | `id` (PK), `universe_uuid` (FK), `url`, `title`, `reason_saved`, `coverage`, `reliability`, `extraction_status` |
| **TimelineEvent** | Event chronology | `id` (PK), `universe_uuid` (FK), `title`, `date`, `era`, `summary`, `description`, `importance`, `confidence` |

---

## Data Flow & Provenance

### Knowledge Integration Flow

```
1. Research Phase
   Researcher Agent → Web Tools → Notebook (Staging DB)

2. Integration Phase
   DB Architect Agent → Notebook → PredicateService
                          ↓
              Normalize Predicates (e.g., "uses" → POWERED_BY)
                          ↓
              Upsert Artifacts & Relations → Main DB

3. Summary Phase
   Universe Chronicler → Main DB → Polished Summary
```

### Provenance Rules

1. **Every Artifact** must have `evidence_refs` linking to `Evidence` records
2. **Predicate Normalization**: Raw predicates mapped to canonical forms via `PredicateService`
3. **Versioning**: `ArtifactVersion` ensures no knowledge is lost during updates
4. **Isolation**: `Extrapolation DB` ensures speculation never contaminates canon

---

## Default Worlds Seed

```json
// backend/app/db/default_worlds.json
{
  "universes": [
    {"name": "Marvel Universe", "franchise": "Marvel", "category": "Superhero"},
    {"name": "DC Universe", "franchise": "DC", "category": "Superhero"},
    {"name": "Star Wars", "franchise": "Star Wars", "category": "Space Opera"},
    // ... more default universes
  ]
}
```

---

## Related Areas

- **Backend Module Map** ([BACKEND.md](BACKEND.md)) - Service/repository layer
- **Architecture Map** ([ARCHITECTURE.md](ARCHITECTURE.md)) - System overview
- **Frontend Map** ([FRONTEND.md](FRONTEND.md)) - Views and data access
- **Agent Documentation** ([../..](../..)) - Agent engine and workflow details

---

*Last Updated: 2026-07-11*
