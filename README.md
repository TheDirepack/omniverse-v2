# Omniverse V2

Research-first fictional-universe knowledge system. FastAPI, SQLAlchemy,
structured model routing, and HTMX.

## Quick Start

```sh
./setup.sh          # Create venv, install deps, create .env.local
./run.sh            # Start backend (uvicorn, :8000, hot-reload)
./run.sh --prod     # Start without hot-reload
./test.sh           # Run V2 tests
./test.sh --ui      # Include UI E2E browser tests
./test.sh --slow    # Include LLM/network tests
./lint.sh           # Ruff linter
./lint.sh --strict  # + mypy, bandit, pylint (if installed)
```

- Virtual environments: `backend/.venv/` or `backend/venv/`
- Environment config: `backend/.env.local`
- Requirements: `backend/requirements.txt`, `backend/requirements-dev.txt`

## Testing

Tests use ephemeral SQLite at `/dev/shm/omniverse_tests/`. V2 tests live in
`backend/tests_v2/` and the test script selects them explicitly.

| Command | What it runs |
|---|---|
| `./test.sh` | Backend unit/integration tests (fast, no network) |
| `./test.sh path/to/test.py` | Specific test file |
| `./test.sh --ui` | Include browser-based E2E tests via cloakbrowser |
| `./test.sh --slow` | Include tests needing LLM or network |
| `./test.sh --prompt-robustness` | Prompt failure mode & robustness tests |

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
- **pytest markers**: `slow` for LLM/network; `asyncio_mode = auto`
- **Log Format**: structured JSONL with run, target, step, world, and model correlation
- **Backend Entry**: `backend/app/main.py` → `backend/app/v2/main.py`
- **Frontend**: HTMX views from `backend/app/v2/views.py` and `backend/app/templates/`
- **CSRF**: Removed (local dev tool)
