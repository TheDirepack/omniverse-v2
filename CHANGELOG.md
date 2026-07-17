# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **New API Structure**: All API endpoints now organized under `/api/v1/` prefix for versioned API support
- **API Documentation**: Comprehensive API documentation in `docs/CODEMAPS/API_DOCS.md` with examples for all endpoints

### Changed
- **API Routes**: All routes migrated from flat `/api/` structure to organized domain-based structure
- **Deprecation**: Old `/api/` endpoints are deprecated and will be removed in a future release

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
