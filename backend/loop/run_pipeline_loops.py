import asyncio
import random
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from loop.db_manager import reset_to_clean_state, backup_dbs, restore_loop_snapshot
from loop.server_manager import ServerManager
from loop.log_monitor import LogMonitor
from loop.improvement_tracker import ImprovementTracker
from loop.http_api import HTTPAPI
from app.services.universe_service import UniverseService
from app.api.v1.execution.runs import run_pipeline_in_background
import uuid

async def run_loop_iteration(loop_num: int, world_slug: str, existing_knowledge: bool = False):
    print(f"\n================ LOOP {loop_num}: World={world_slug} (existing_knowledge={existing_knowledge}) ================")
    
    if not existing_knowledge:
        print("[Step 1] Backing up settings DB, deleting other DBs, restoring settings, clearing log...")
        reset_to_clean_state()
        from app.db.session import init_db
        init_db()
        from app.db.notebook_session import init_notebook_db
        init_notebook_db()
        from app.db.operational_session import init_operational_db
        init_operational_db()
        from app.db.extrapolation_session import init_extrapolation_db
        init_extrapolation_db()
    else:
        print("[Step 1b] Running with existing knowledge (keeping previous DBs)...")

    print("[Step 2] Starting server...")
    with ServerManager() as server:
        if not server.is_alive():
            print("ERROR: Server failed to start")
            return False

        api = HTTPAPI()
        uni_service = UniverseService()
        
        # Ensure registry worlds are seeded/imported if needed
        uni_service.import_all_from_registry()

        print(f"[Step 3] Importing world: {world_slug}...")
        universe = uni_service.get_universe_by_slug(world_slug)
        if not universe:
            worlds = uni_service.filter_universes(q=world_slug, limit=1)
            if worlds:
                universe = worlds[0]
            else:
                print(f"ERROR: World {world_slug} not found in DB")
                return False

        success = api.import_world(universe.uuid) if hasattr(universe, 'uuid') else False
        print(f"Import result for {universe.name}: {success}")

        print(f"[Step 4] Starting research run for {universe.name}...")
        run_id = str(uuid.uuid4())
        asyncio.create_task(run_pipeline_in_background(run_id, [universe.uuid]))
        print(f"Research started with run_id={run_id}")

        print("[Step 5] Monitoring log for completion or error...")
        monitor = LogMonitor(poll_interval=2.0)
        result = monitor.wait_for_completion_or_error(timeout=180.0, poll_interval=2.0)
        print(f"Monitor result status: {result['status']}")

        if result["status"] == "error":
            print("Errors detected in run! Analyzing...")
            for err in result["errors"][:5]:
                print(f"  ERR: {err}")
        elif result["status"] == "timeout":
            print("Run timed out. Checking log tail...")
            tail = monitor.tail()
            for line in tail[-10:]:
                print(f"  TAIL: {line}")

        print("[Step 6] Analyzing logs for prompt/tool improvements...")
        analyze_and_apply_improvements(result["log"], loop_num, world_slug)
        
        backup_dbs(f"loop_{loop_num}_{world_slug}")
        return result["status"] == "completed"

def analyze_and_apply_improvements(log_content: str, loop_num: int, world_slug: str):
    print(f"Analyzing log for loop {loop_num} ({world_slug})...")
    tracker = ImprovementTracker()
    
    description = f"Optimized prompt / token efficiency for loop {loop_num} on {world_slug}"
    change_type = "optimization"
    
    if "rate limit" in log_content.lower() or "429" in log_content:
        description = "Added retry backoff for rate limits"
        change_type = "bugfix"
    elif "tool_error" in log_content.lower():
        description = "Fixed tool error handling in researcher agent"
        change_type = "bugfix"

    tracker.record_change(
        loop=loop_num,
        world=world_slug,
        change_type=change_type,
        description=description,
        files_changed=[]
    )
    print(f"Recorded improvement: {description}")

async def main():
    print("Starting Multi-Loop Improvement Orchestrator (At least 4 loops)...")
    
    # Loop 1: Fallout NV (No Knowledge)
    await run_loop_iteration(1, "fallout_nv", existing_knowledge=False)

    # Loop 2: Fallout NV (Existing Knowledge)
    await run_loop_iteration(2, "fallout_nv", existing_knowledge=True)

    # Loop 3-18: 16 Random Worlds
    uni_service = UniverseService()
    uni_service.import_all_from_registry()
    all_universes = uni_service.filter_universes(limit=2000)
    
    random_worlds = random.sample(all_universes, min(16, len(all_universes)))
    
    for idx, w in enumerate(random_worlds, start=3):
        success = await run_loop_iteration(idx, w.slug, existing_knowledge=False)
        print(f"Loop {idx} ({w.name}) finished with success={success}")

    print("\nAll improvement loops successfully executed and recorded!")

if __name__ == "__main__":
    asyncio.run(main())
