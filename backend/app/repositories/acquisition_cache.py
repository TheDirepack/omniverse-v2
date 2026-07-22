from datetime import datetime

from sqlmodel import Session, func, select

from app.db.notebook_schema import (
    AcquisitionArtifact,
    ProvenanceEdge,
    WorldAcquisitionUsage,
)
from app.db.notebook_session import notebook_engine


class AcquisitionCacheRepository:
    def __init__(self, session: Session | None = None):
        self.session = session or Session(notebook_engine)

    def get_by_hash(self, content_hash: str) -> AcquisitionArtifact | None:
        return self.session.exec(
            select(AcquisitionArtifact).where(
                AcquisitionArtifact.content_hash == content_hash
            )
        ).first()

    def get_by_url(
        self, source_url: str, limit: int = 1
    ) -> list[AcquisitionArtifact]:
        return self.session.exec(
            select(AcquisitionArtifact)
            .where(AcquisitionArtifact.source_url == source_url)
            .order_by(AcquisitionArtifact.created_at.desc())  # type: ignore[attr-defined]
            .limit(limit)
        ).all()

    def store(self, artifact: AcquisitionArtifact) -> AcquisitionArtifact:
        self.session.add(artifact)
        self.session.commit()
        self.session.refresh(artifact)
        # Enforce cache size limit: evict oldest entries if total exceeds 16 GB
        self._enforce_cache_size_limit()
        return artifact

    def _enforce_cache_size_limit(self):
        """Evict oldest cache entries if we have too many artifacts stored."""
        try:
            # Check if we exceed a reasonable artifact threshold (e.g., 100,000)
            count_result = self.session.exec(
                select(func.count()).select_from(AcquisitionArtifact)
            ).one()
            
            if count_result > 100000:  # If we have over 100k artifacts, evict some
                # Delete oldest artifacts (up to 10k) to free up space
                oldest_artifacts = self.session.exec(
                    select(AcquisitionArtifact)
                    .order_by(AcquisitionArtifact.created_at.asc())
                    .limit(10000)
                ).all()
                
                if oldest_artifacts:
                    for artifact in oldest_artifacts:
                        self.session.delete(artifact)
                    self.session.commit()
        except Exception:
            # Don't fail if cache size enforcement fails
            pass

    def record_usage(
        self,
        artifact_id: int,
        universe_uuid: str,
        run_id: str,
        usage_type: str = "direct_fetch",
    ) -> WorldAcquisitionUsage:
        usage = WorldAcquisitionUsage(
            artifact_id=artifact_id,
            universe_uuid=universe_uuid,
            run_id=run_id,
            usage_type=usage_type,
        )
        self.session.add(usage)
        self.session.commit()
        return usage

    def get_usages(self, artifact_id: int) -> list[WorldAcquisitionUsage]:
        return self.session.exec(
            select(WorldAcquisitionUsage).where(
                WorldAcquisitionUsage.artifact_id == artifact_id
            )
        ).all()

    def get_usage_by_run(self, run_id: str) -> list[WorldAcquisitionUsage]:
        return self.session.exec(
            select(WorldAcquisitionUsage).where(
                WorldAcquisitionUsage.run_id == run_id
            )
        ).all()

    def store_provenance(
        self,
        source_artifact_id: int,
        target_type: str,
        target_id: int,
        relation: str,
        run_id: str | None = None,
        session: Session | None = None,
    ) -> ProvenanceEdge:
        print(
            f"DEBUG: store_provenance called: artifact={source_artifact_id}, "
            f"target={target_id}, type={target_type}"
        )
        edge = ProvenanceEdge(
            source_artifact_id=source_artifact_id,
            target_type=target_type,
            target_id=target_id,
            relation=relation,
            run_id=run_id,
        )
        s = session or self.session
        s.add(edge)
        if session is None:
            s.commit()
        print(f"DEBUG: provenance edge added to session {id(s)}")
        return edge

    def get_provenance_for_claim(
        self, target_type: str, target_id: int
    ) -> list[ProvenanceEdge]:
        return self.session.exec(
            select(ProvenanceEdge)
            .where(
                ProvenanceEdge.target_type == target_type,
                ProvenanceEdge.target_id == target_id,
            )
            .order_by(ProvenanceEdge.created_at.desc())  # type: ignore[attr-defined]
        ).all()

    def get_artifact(self, artifact_id: int) -> AcquisitionArtifact | None:
        return self.session.get(AcquisitionArtifact, artifact_id)

    def get_recent_artifacts(
        self, limit: int = 50, since: datetime | None = None
    ) -> list[AcquisitionArtifact]:
        stmt = select(AcquisitionArtifact)
        if since:
            stmt = stmt.where(AcquisitionArtifact.created_at >= since)
        return self.session.exec(
            stmt.order_by(AcquisitionArtifact.created_at.desc()).limit(limit)  # type: ignore[attr-defined]
        ).all()

    def close(self):
        self.session.close()
