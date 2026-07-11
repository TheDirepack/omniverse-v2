import asyncio
from collections import OrderedDict
from enum import Enum

from sqlmodel import Session

from app.db.unconfirmed_schema import AcquisitionArtifact
from app.repositories.acquisition_cache import AcquisitionCacheRepository


class FreshnessPolicy(Enum):
    CACHE_ONLY = "cache_only"
    PREFER_CACHE = "prefer_cache"
    FORCE_REFRESH = "force_refresh"


MAX_LRU_SIZE = 500


class AcquisitionCache:
    def __init__(self, repo: AcquisitionCacheRepository | None = None):
        self.repo = repo or AcquisitionCacheRepository()
        self._lru: OrderedDict[str, AcquisitionArtifact] = OrderedDict()
        self._pending: dict[str, asyncio.Future] = {}
        self._pending_hash: dict[str, asyncio.Future] = {}

    def get_from_lru(self, url: str) -> AcquisitionArtifact | None:
        if url in self._lru:
            self._lru.move_to_end(url)
            return self._lru[url]
        return None

    def _set_lru(self, url: str, artifact: AcquisitionArtifact):
        self._lru[url] = artifact
        self._lru.move_to_end(url)
        if len(self._lru) > MAX_LRU_SIZE:
            self._lru.popitem(last=False)

    def clear_lru(self):
        self._lru.clear()

    async def get(
        self,
        url: str,
        policy: FreshnessPolicy = FreshnessPolicy.PREFER_CACHE,
        do_fetch=None,
    ) -> tuple[AcquisitionArtifact | None, str]:
        in_memory = self.get_from_lru(url)
        if in_memory and policy != FreshnessPolicy.FORCE_REFRESH:
            return in_memory, "lru_hit"

        persistent = self.repo.get_by_url(url, limit=1)
        if persistent:
            existing = persistent[0]
            self._set_lru(url, existing)
            if policy == FreshnessPolicy.CACHE_ONLY:
                return existing, "cache_hit"
            if policy == FreshnessPolicy.PREFER_CACHE:
                return existing, "cache_hit"

        if policy == FreshnessPolicy.CACHE_ONLY:
            return None, "cache_miss"

        if not do_fetch:
            return None, "no_fetch_provided"

        if url in self._pending:
            artifact = await self._pending[url]
            return artifact, "deduped_fetch"

        future = asyncio.get_event_loop().create_future()
        self._pending[url] = future
        try:
            artifact = await do_fetch()
            if artifact:
                stored = self.repo.store(artifact)
                self._set_lru(url, stored)
                future.set_result(stored)
                return stored, "fetched"
            future.set_result(None)
            return None, "fetch_failed"
        except Exception as e:
            if not future.done():
                future.set_exception(e)
            raise
        finally:
            self._pending.pop(url, None)

    async def get_by_hash(
        self, content_hash: str
    ) -> AcquisitionArtifact | None:
        return self.repo.get_by_hash(content_hash)

    def record_usage(
        self,
        artifact_id: int,
        universe_uuid: str,
        run_id: str,
        usage_type: str = "direct_fetch",
    ):
        self.repo.record_usage(
            artifact_id=artifact_id,
            universe_uuid=universe_uuid,
            run_id=run_id,
            usage_type=usage_type,
        )

    def store_provenance(
        self,
        source_artifact_id: int,
        target_type: str,
        target_id: int,
        relation: str,
        run_id: str | None = None,
        session: Session | None = None,
    ):
        self.repo.store_provenance(
            source_artifact_id=source_artifact_id,
            target_type=target_type,
            target_id=target_id,
            relation=relation,
            run_id=run_id,
            session=session,
        )

    def close(self):
        self.repo.close()


acquisition_cache = AcquisitionCache()
