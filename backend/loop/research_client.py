import asyncio
import time

import httpx

from loop.loop_config import SERVER_URL


class ResearchClient:
    def __init__(self, base_url: str = SERVER_URL):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url, timeout=30)

    async def close(self):
        await self.client.aclose()

    async def import_world(self, world_id: str) -> dict:
        r = await self.client.post(f"/worlds/import/{world_id}")
        r.raise_for_status()
        return {"status": "imported", "world_id": world_id}

    async def start_research(self, world_name: str) -> dict:
        from app.services.universe_service import UniverseService
        uni_service = UniverseService()
        universe = uni_service.get_universe_by_slug(world_name)
        if not universe:
            worlds = uni_service.filter_universes(q=world_name, limit=1)
            if not worlds:
                return {"error": f"World {world_name} not found"}
            universe = worlds[0]

        import uuid
        from app.api.v1.execution.runs import run_pipeline_in_background

        run_id = str(uuid.uuid4())
        asyncio.create_task(run_pipeline_in_background(run_id, [universe.uuid]))
        return {"run_id": run_id, "world": universe.name}

    async def get_active_runs(self) -> list[str]:
        try:
            r = await self.client.get("/research/queue")
            return []
        except Exception:
            return []

    async def get_run_status(self, run_id: str) -> dict | None:
        try:
            r = await self.client.get(f"/research/results/{run_id}")
            if r.status_code == 200:
                return {"exists": True, "text": r.text[:500]}
            return {"exists": False}
        except httpx.HTTPError:
            return None

    async def import_world_http(self, world_id: str) -> bool:
        try:
            r = await self.client.post(f"/worlds/import/{world_id}")
            return r.status_code == 200
        except Exception:
            return False

    async def health_check(self) -> bool:
        try:
            r = await self.client.get("/api/health", timeout=5)
            return r.status_code == 200
        except Exception:
            return False
