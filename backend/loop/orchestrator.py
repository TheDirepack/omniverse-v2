"""
Loop Orchestrator - CLI for managing optimization loops.

Usage:
    python -m loop.orchestrator reset                    # Reset DBs to clean state
    python -m loop.orchestrator start                    # Start server
    python -m loop.orchestrator stop                     # Stop server
    python -m loop.orchestrator import <id>              # Import a world
    python -m loop.orchestrator start-research <name>    # Start research on world
    python -m loop.orchestrator monitor <timeout>        # Monitor log for completion/error
    python -m loop.orchestrator log-stats                # Print log stats
    python -m loop.orchestrator db-stats                 # Print DB stats
    python -m loop.orchestrator backup <tag>             # Backup all DBs
    python -m loop.orchestrator restore <tag>            # Restore DBs from backup
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

LOOP_DIR = Path(__file__).resolve().parent
BASE_DIR = LOOP_DIR.parent
DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = DATA_DIR / "backup"
LOGS_DIR = BASE_DIR / "logs"
AGENT_LOG = LOGS_DIR / "agents.log"


def _find_venv():
    for venv_name in [".venv", "venv"]:
        p = BASE_DIR / venv_name
        if p.exists():
            return p
        p2 = BASE_DIR / "backend" / venv_name
        if p2.exists():
            return p2
    raise RuntimeError("No venv found")


def _get_env():
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{BASE_DIR / 'backend'}:{env.get('PYTHONPATH', '')}"
    return env


def cmd_reset():
    """Backup settings, delete all other DBs, restore settings, clear log."""
    from loop.db_manager import reset_to_clean_state
    reset_to_clean_state()
    print("OK: Reset to clean state (settings preserved)")


def cmd_start():
    """Start the uvicorn server in background."""
    venv = _find_venv()
    env = _get_env()
    env["APP_LOG_LEVEL"] = "DEBUG"

    log_dir = LOGS_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_log = log_dir / "server_stdout.log"

    proc = subprocess.Popen(
        [
            str(venv / "bin" / "uvicorn"),
            "app.main:app",
            "--app-dir", str(BASE_DIR / "backend"),
            "--host", "127.0.0.1",
            "--port", "8000",
            "--reload",
        ],
        env=env,
        stdout=open(stdout_log, "w"),
        stderr=subprocess.STDOUT,
    )
    print(f"OK: Server starting (PID {proc.pid})")
    # Wait for health
    import httpx
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            r = httpx.get("http://127.0.0.1:8000/api/health", timeout=2)
            if r.status_code == 200:
                print("OK: Server is healthy")
                return
        except Exception:
            pass
        time.sleep(0.5)
    print("ERROR: Server failed to start in time")


def cmd_stop():
    """Kill all uvicorn processes."""
    subprocess.run(
        ["pkill", "-f", "uvicorn app.main:app"],
        capture_output=True, timeout=5
    )
    time.sleep(1)
    print("OK: Server stopped")


def cmd_import(world_id: str):
    """Import a world from the registry via API."""
    import httpx
    try:
        r = httpx.post(f"http://127.0.0.1:8000/worlds/import/{world_id}", timeout=10)
        if r.status_code == 200:
            print(f"OK: World {world_id} imported")
        else:
            print(f"WARN: Import response {r.status_code}")
    except Exception as e:
        print(f"ERROR: Import failed: {e}")


def cmd_start_research(world_name: str):
    """Start a research pipeline run for a world."""
    sys.path.insert(0, str(BASE_DIR / "backend"))
    import uuid
    import asyncio
    from app.services.universe_service import UniverseService
    from app.api.v1.execution.runs import run_pipeline_in_background

    uni_service = UniverseService()
    universe = uni_service.get_universe_by_slug(world_name)
    if not universe:
        worlds = uni_service.filter_universes(q=world_name, limit=1)
        if not worlds:
            print(f"ERROR: World '{world_name}' not found")
            return
        universe = worlds[0]

    run_id = str(uuid.uuid4())
    print(f"Starting research run {run_id} for {universe.name}")
    asyncio.run(run_pipeline_in_background(run_id, [universe.uuid]))
    print(f"OK: Research started (run_id={run_id})")


def cmd_monitor(timeout_str: str = "600"):
    """Monitor the agent log for completion or error."""
    timeout = float(timeout_str)
    from loop.log_monitor import LogMonitor
    monitor = LogMonitor()
    result = monitor.wait_for_completion_or_error(timeout=timeout, poll_interval=3.0)
    print(f"STATUS: {result['status']}")
    if result.get("errors"):
        print("ERRORS:")
        for e in result["errors"]:
            print(f"  {e}")
    return result


def cmd_log_stats():
    """Show key stats from the agent log."""
    log_path = AGENT_LOG
    if not log_path.exists():
        print("No agent log found")
        return

    content = log_path.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()
    total = len(lines)

    failed = sum(1 for l in lines if "[FAILED]" in l)
    completed = sum(1 for l in lines if "[COMPLETED]" in l)
    prompts = sum(1 for l in lines if "[PROMPT]" in l)
    tool_req = sum(1 for l in lines if "[TOOL_REQ]" in l)
    tool_res = sum(1 for l in lines if "[TOOL_RES]" in l)

    print(f"Total log lines: {total}")
    print(f"  FAILED: {failed}")
    print(f"  COMPLETED: {completed}")
    print(f"  PROMPT events: {prompts}")
    print(f"  TOOL_REQ events: {tool_req}")
    print(f"  TOOL_RES events: {tool_res}")

    # Extract unique agents
    agents = set()
    for l in lines:
        parts = l.split("] [")
        if len(parts) >= 3:
            agents.add(parts[1].lstrip("["))
    print(f"  Unique agents: {', '.join(sorted(agents))}")

    # Word count
    word_count = sum(len(l.split()) for l in lines)
    print(f"  Total words: {word_count}")


def cmd_db_stats():
    """Show size of each database."""
    from loop.db_manager import get_all_db_sizes, get_world_count, get_main_db_artifact_count, get_notebook_artifact_count
    sizes = get_all_db_sizes()
    for name, size in sizes.items():
        print(f"  {name}.db: {size / 1024:.1f} KB")
    print(f"  Worlds: {get_world_count()}")
    print(f"  Main DB Artifacts: {get_main_db_artifact_count()}")
    print(f"  Notebook Artifacts: {get_notebook_artifact_count()}")


def cmd_backup(tag: str):
    """Backup all DBs to loop_snapshots."""
    from loop.db_manager import backup_dbs
    path = backup_dbs(tag)
    print(f"OK: Backed up to {path}")


def cmd_restore(tag: str):
    """Restore DBs from loop_snapshots."""
    from loop.db_manager import restore_loop_snapshot
    if restore_loop_snapshot(tag):
        print(f"OK: Restored from {tag}")
    else:
        print(f"ERROR: No snapshot found for {tag}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    commands = {
        "reset": lambda: cmd_reset(),
        "start": lambda: cmd_start(),
        "stop": lambda: cmd_stop(),
        "import": lambda: cmd_import(sys.argv[2]) if len(sys.argv) > 2 else print("Usage: import <world_id>"),
        "start-research": lambda: cmd_start_research(" ".join(sys.argv[2:])) if len(sys.argv) > 2 else print("Usage: start-research <world_name>"),
        "monitor": lambda: cmd_monitor(sys.argv[2] if len(sys.argv) > 2 else "600"),
        "log-stats": lambda: cmd_log_stats(),
        "db-stats": lambda: cmd_db_stats(),
        "backup": lambda: cmd_backup(sys.argv[2]) if len(sys.argv) > 2 else print("Usage: backup <tag>"),
        "restore": lambda: cmd_restore(sys.argv[2]) if len(sys.argv) > 2 else print("Usage: restore <tag>"),
    }

    if command not in commands:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)

    commands[command]()
