# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Living Notebook**: Fully implemented staging notebook with real-time artifact inspection, claim editing, and seamless DB promotion
- **Knowledge Graph Research Frontier Refactor**: Enhanced knowledge graph exploration, frontier tracking, and neighborhood query optimization
- **Source Annotations**: Grounded provenance linking with support counts, evidence references, and URI traceability
- **Best-of-Both-Worlds Researcher Prompt**: Unified agent prompt combining deep exploratory reasoning with structured schema extraction and verification
- **New API Structure**: All API endpoints now organized under `/api/v1/` prefix for versioned API support
- **API Documentation**: Comprehensive API documentation in `docs/CODEMAPS/API_DOCS.md` with examples for all endpoints
- **Settings UI tests**: 12 settings UI tests covering provider CRUD, sync, keys, routes, health, and general settings

### Fixed
- **Settings JS routing** (`1c8f045`): Fixed `selectProvider`, `selectRoute`, `addProviderKey`, and `syncModels` URL paths pointing to correct view endpoints (not broken `/api/v1/settings/` routes)
- **Route edit form action**: Changed `hx-post` target from `/settings/agent-routes` to `/settings/routes/upsert`
- **Removed dead code**: Cleaned up duplicate `showToast`, `toggleMobileSidebar`, `closeMobileDrawer`, `ErrorTemplate`, and HTMX error handlers from `settings.html` and `base.html`
- **syncModels error handling** (`httpx.HTTPStatusError`): Added proper exception handling for provider model sync with uncaught `httpx` errors
- **Snapshot template path**: Fixed `TemplateNotFound` for `world_snapshots.html` by adding `components/` prefix
- **Snapshot URL prefix**: `world_snapshots.html` now uses `snapshot_url_prefix` template variable (shared between `/settings/` and `/worlds/` contexts)
- **Add key 422 error**: `addProviderKey()` changed from `FormData` to plain JS object for HTMX `values` parameter compatibility
- **Test updates** (`b96ff3e`): Updated settings UI tests to use unique names, hidden input ID extraction, and correct view-formatted routes

### Changed
- **API Routes**: All routes migrated from flat `/api/` structure to organized domain-based structure
- **Docs cleanup**: Archived stale implementation reports and superpower plans to `docs/archive/`; updated all codemaps to reflect current codebase state (7 files)

## [2.0.0] - 2026-07-16

### Added
- Multi-agent fictional power-tiering platform capabilities
- LangGraph-based agent orchestration
- HTMX-based frontend
- Knowledge Graph with Artifact-based provenance
- Five database systems (Main, Staging, Settings, Operational, Extrapolation)

### Changed
- React frontend replaced with HTMX server-side rendering
- Database structure expanded for multiple use cases
