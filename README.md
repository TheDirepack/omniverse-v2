# Omniverse V2

Research-first fictional-universe knowledge system. FastAPI, SQLAlchemy,
structured model routing, and HTMX.

## Quick Start

```sh
./setup.sh          # Create venv, install deps, create .env.local
./run.sh            # Start backend (uvicorn, :8000, hot-reload)
./run.sh --prod     # Start without hot-reload
./test.sh           # Run V2 tests
./test.sh --ui      # Run HTTP/template UI tests (no real browser)
./test.sh --slow    # Include slow tests; still offline
./test.sh --evaluation # Include deterministic evaluation tests; still offline
./lint.sh           # Ruff linter
./lint.sh --strict  # + mypy, bandit, pylint (if installed)
```

- Virtual environments: `backend/.venv/` or `backend/venv/`
- Environment config: `backend/.env.local`
- Requirements: `backend/requirements.txt`, `backend/requirements-dev.txt`

## Testing

Tests use isolated temporary SQLite databases. V2 tests live in
`backend/tests_v2/` and the test script selects them explicitly.

| Command | What it runs |
|---|---|
| `./test.sh` | Unit, integration, and HTTP/template UI tests; excludes slow, evaluation, network, and live |
| `./test.sh backend/tests_v2/test_api.py` | Specific V2 test file |
| `./test.sh --ui` | HTTP/template UI tests only, using TestClient rather than a real browser |
| `./test.sh --slow` | Also includes slow tests; excludes evaluation, network, and live |
| `./test.sh --evaluation` | Also includes slow and evaluation tests; excludes network and live |
| `./test.sh backend/tests_v2/test_live_reference.py -m live` | Explicitly opts into real endpoint calls; requires network access |

The `slow` and `evaluation` markers do not grant network access. Tests must
declare `live` or `network` and be explicitly selected to use external endpoints.
Offline passes verify fixture-backed behavior, not live provider availability
or real-world research quality. See the [V2 audit report](docs/AUDIT_V2.md).

**Test locations:**

- V2 tests: `backend/tests_v2/`
- V2 UI tests: `backend/tests_v2/ui/`

## Linting

```sh
./lint.sh              # Ruff (config in backend/pyproject.toml)
./lint.sh --strict     # + mypy, bandit, pylint
```

## Architecture Highlights

The deployed application is `backend/app/v2/`; `backend/app/main.py` delegates
to the V2 application factory.

- **Research workflow**: durable run kernel with inventory, planning, search,
  acquisition, extraction, synthesis, audit, integration, and completion steps.
- **Persistence**: one Alembic-managed SQLite database plus blob and protected
  credential directories under `backend/data/`.
- **Evidence policy**: only accepted, provenance-backed evidence may promote to
  canon; workspace research remains provisional.
- **Routing**: database-driven provider/model fallback. Qwen is the normal final
  provider fallback; MiniCPM is a fetch/readability helper.
- **Logs**: `backend/logs/agent.jsonl`, `server.jsonl`, and
  `remote-server.jsonl`.

## API

JSON endpoints are mounted at `/api/v2/`; HTML/HTMX views are unversioned.
See the [canonical V2 codemaps](docs/CODEMAPS_V2/INDEX.md) for architecture,
runtime, persistence, API/view, and operations references. See
[`docs/index.md`](docs/index.md) for the full documentation map and historical material.

## Key Conventions

- **API Prefix**: `/api/v2/`
- **CORS**: Wide open (`*`) — local dev tool
- **pytest markers**: `slow` and `evaluation` are offline by default; `live` and `network` require explicit selection
- **Log Format**: structured JSONL with run, target, step, world, and model correlation
- **Backend Entry**: `backend/app/main.py` → `backend/app/v2/main.py`
- **Frontend**: HTMX views from `backend/app/v2/views.py` and `backend/app/templates/`
- **CSRF**: Removed (local dev tool)
