# Omniverse V2 Documentation

**Last Updated:** 2026-07-22

## Documentation Map

### Architecture & Reference (CODEMAPS)

| Document | Description |
| :--- | :--- |
| [Codemaps Index](CODEMAPS/INDEX.md) | Table of contents for all codemaps |
| [System Architecture](CODEMAPS/ARCHITECTURE.md) | Layered architecture, agents, database topology |
| [Backend Module Map](CODEMAPS/BACKEND.md) | FastAPI modules, services, repositories, views |
| [Database Schema](CODEMAPS/DATABASE.md) | All 6 SQLite databases and their tables |
| [Frontend Structure](CODEMAPS/FRONTEND.md) | HTMX views, templates, JS architecture |
| [File Registry](CODEMAPS/FILES.md) | Complete directory structure |
| [API Documentation](CODEMAPS/API_DOCS.md) | REST API (`/api/v1/`) and HTMX view routes |

### UI/UX Design

| Document | Description |
| :--- | :--- |
| [Design System](UI/01_design_system.md) | Visual language, color, typography, UX principles |
| [UI Architecture](UI/02_ui_architecture.md) | Shell, navigation, filters, HTMX strategy |
| [Component Spec](UI/03_component_specification.md) | Exact Tailwind classes for all components |
| [Workflow Spec](UI/04_workflow_specification.md) | Per-page compositions and interactions |

### Agent Documentation

- [AGENTS.md](../AGENTS.md) — Agent engine, tool loop, LLM routing, pipeline, testing

### Historical Archive

| Document | Original Date |
| :--- | :--- |
| [Implementation Spec](archive/IMPLEMENTATION_SPEC.md) | 2026-07-11 |
| [Implementation Progress](archive/IMPLEMENTATION_PROGRESS.md) | 2026-07-16 |
| [Implementation Summary](archive/IMPLEMENTATION_SUMMARY.md) | 2026-07-16 |
| [Changes Made](archive/CHANGES_MADE.md) | 2026-07-16 |
| [Final Implementation Report](archive/FINAL_IMPLEMENTATION_REPORT.md) | 2026-07-16 |
| [ADR-0001: Research Results Viewer](archive/adr/ADR-0001-research-results-viewer.md) | 2026-07-16 |
| [Superpower Plans](archive/superpowers/) | 2026-07-12 |

## Quick Start

```sh
./setup.sh          # Create venv, install deps
./run.sh            # Start uvicorn on :8000
./test.sh           # Run pytest
./lint.sh           # Ruff linting
```

## Testing

```sh
./test.sh                   # Standard tests
./test.sh --slow            # Include LLM/network tests
./test.sh --ui              # Include HTMX E2E tests
./test.sh path/to/test.py   # Specific test file
```
