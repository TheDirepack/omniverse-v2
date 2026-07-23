import httpx
from loop.loop_config import SERVER_URL


class HTTPAPI:
    def __init__(self, base_url: str = SERVER_URL):
        self.base_url = base_url

    def import_world(self, world_id: str) -> bool:
        with httpx.Client(base_url=self.base_url, timeout=10) as c:
            r = c.post(f"/worlds/import/{world_id}")
            return r.status_code == 200

    def health_check(self) -> bool:
        with httpx.Client(base_url=self.base_url, timeout=5) as c:
            try:
                r = c.get("/api/health")
                return r.status_code == 200
            except Exception:
                return False
