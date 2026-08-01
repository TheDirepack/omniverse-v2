# Omniverse V2 Documentation

**Current runtime:** V2 research system.

## Documentation Map

### Current V2

- [V2 codemaps](CODEMAPS_V2/INDEX.md) — canonical source-backed runtime map
- [Architecture](CODEMAPS_V2/ARCHITECTURE.md) — facade, factory, boundaries, and deferred scope
- [Runtime and research](CODEMAPS_V2/RUNTIME_AND_RESEARCH.md) — workflow, routing, MiniCPM, and browsing
- [Persistence](CODEMAPS_V2/PERSISTENCE.md) — SQLite, Alembic, blobs, credentials, and resets
- [API and views](CODEMAPS_V2/API_AND_VIEWS.md) — `/api/v2` and unversioned HTMX routes
- [Operations](CODEMAPS_V2/OPERATIONS.md) — lifecycle, JSONL logs, commands, and tests
- [Research validation loop](RESEARCH_VALIDATION_LOOP_PROMPT.md)
- [Progress record](rebuild/PROGRESS.md)

### Agent Documentation

- [AGENTS.md](../AGENTS.md) — deployed V2 boundaries, runtime, operations, and conventions

### Historical Archive

| Document | Original Date |
| :--- | :--- |
| [Implementation Spec](archive/IMPLEMENTATION_SPEC.md) | 2026-07-11 |
| [Implementation Progress](archive/IMPLEMENTATION_PROGRESS.md) | 2026-07-16 |
| [Implementation Summary](archive/IMPLEMENTATION_SUMMARY.md) | 2026-07-16 |
| [Changes Made](archive/CHANGES_MADE.md) | 2026-07-16 |
| [Final Implementation Report](archive/FINAL_IMPLEMENTATION_REPORT.md) | 2026-07-16 |
| [HTMX-to-API Contract Analysis](archive/audits/OMNIVERSE-V2-HTMX-API-CONTRACT-FINAL.md) | 2026-07-27 |
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
