from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, select

from app.db.notebook_schema import (
    NotebookClaim,
    NotebookEntry,
    ResearchSource,
    VisitedUrl,
)
from app.db.notebook_session import notebook_engine
from app.services.universe_service import UniverseService


class WorkspaceService:
    def __init__(self, session: Optional[Session] = None, universe_service: Optional[UniverseService] = None):
        self.session = session or Session(notebook_engine)
        self.universe_service = universe_service

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            self.session.close()

    # --- Notebook Management ---

    def get_notebook_index(self, universe_uuid: str) -> list[NotebookEntry]:
        """Returns a list of notebook entries (summaries) for a world."""
        statement = (
            select(NotebookEntry)
            .where(NotebookEntry.universe_uuid == universe_uuid)
            .order_by(NotebookEntry.priority)
        )
        return self.session.exec(statement).all()

    def get_notebook_index_str(self, universe_uuid: str, limit: int = 50) -> str:
        """Generates a concise list of notebook entries for the agent's context."""
        entries = self.get_notebook_index(universe_uuid)
        if not entries:
            return "No active research notes."

        display_entries = entries[:limit]
        lines = [
            f"[{e.id}] {e.title} (Status: {e.status}, Priority: {e.priority})"
            for e in display_entries
        ]

        result = "RESEARCH NOTES:\n" + "\n".join(lines)
        if len(entries) > limit:
            result += f"\n(... and {len(entries) - limit} more. Use loadNotebookEntry with entry_id to see details ...)"
        return result

    def get_notebook_content(self, run_id: Optional[str], universe_uuid: str) -> str:
        """Returns the concatenated summaries of notebook entries for a world.
        If run_id is provided, it filters by run; otherwise, it returns all persistent notes.
        """
        statement = select(NotebookEntry.summary).where(
            NotebookEntry.universe_uuid == universe_uuid
        )
        if run_id:
            statement = statement.where(NotebookEntry.run_id == run_id)

        statement = statement.order_by(NotebookEntry.priority)
        summaries = self.session.exec(statement).all()
        return "\n".join(filter(None, summaries))

    def get_notebook_entry(self, entry_id: Optional[int] = None, key: Optional[str] = None, universe_uuid: Optional[str] = None) -> Optional[NotebookEntry]:
        """Returns a full notebook entry by ID or by (universe_uuid, key) latest version."""
        if entry_id is not None:
            return self.session.get(NotebookEntry, entry_id)
        if key is not None and universe_uuid is not None:
            statement = (
                select(NotebookEntry)
                .where(NotebookEntry.universe_uuid == universe_uuid, NotebookEntry.key == key)
                .order_by(NotebookEntry.version.desc())
            )
            return self.session.exec(statement).first()
        return None

    def search_notebook_entries(
        self,
        universe_uuid: str,
        query: Optional[str] = None,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        key: Optional[str] = None,
    ) -> list[NotebookEntry]:
        """Searches notebook entries with filters."""
        statement = select(NotebookEntry).where(NotebookEntry.universe_uuid == universe_uuid)
        if kind:
            statement = statement.where(NotebookEntry.kind == kind)
        if status:
            statement = statement.where(NotebookEntry.status == status)
        if key:
            statement = statement.where(NotebookEntry.key == key)
        if query:
            q_pattern = f"%{query}%"
            statement = statement.where(
                (NotebookEntry.title.ilike(q_pattern)) |
                (NotebookEntry.summary.ilike(q_pattern)) |
                (NotebookEntry.details.ilike(q_pattern))
            )
        statement = statement.order_by(NotebookEntry.priority.desc(), NotebookEntry.updated_at.desc())
        return self.session.exec(statement).all()

    def delete_notebook_entry(self, entry_id: int) -> bool:
        """Deletes a notebook entry."""
        entry = self.session.get(NotebookEntry, entry_id)
        if entry:
            self.session.delete(entry)
            self.session.commit()
            return True
        return False

    def upsert_notebook_entry(
        self,
        universe_uuid: str,
        title: str,
        summary: str,
        kind: str = "GENERAL",
        run_id: Optional[str] = None,
        details: Optional[str] = None,
        status: str = "OPEN",
        priority: int = 0,
        entry_id: Optional[int] = None,
        key: Optional[str] = None,
        confidence: Optional[float] = None,
        expected_information: Optional[str] = None,
        discovered_from: Optional[str] = None,
        relationship_type: Optional[str] = None,
    ) -> NotebookEntry:
        """Creates or updates a notebook entry, supporting key-based versioning."""
        # 1. If entry_id is explicitly provided, update that entry
        if entry_id is not None:
            entry = self.session.get(NotebookEntry, entry_id)
            if entry:
                entry.title = title
                entry.summary = summary
                entry.details = details
                entry.kind = kind
                entry.status = status
                entry.priority = priority
                entry.run_id = run_id
                if key is not None:
                    entry.key = key
                if confidence is not None:
                    entry.confidence = confidence
                if expected_information is not None:
                    entry.expected_information = expected_information
                if discovered_from is not None:
                    entry.discovered_from = discovered_from
                if relationship_type is not None:
                    entry.relationship_type = relationship_type
                entry.updated_at = datetime.now(timezone.utc)
                self.session.add(entry)
                self.session.commit()
                self.session.refresh(entry)
                return entry

        # 2. If key is provided, look up the latest version for this universe and key
        if key is not None:
            existing = self.session.exec(
                select(NotebookEntry)
                .where(NotebookEntry.universe_uuid == universe_uuid, NotebookEntry.key == key)
                .order_by(NotebookEntry.version.desc())
            ).first()
            if existing:
                new_version = existing.version + 1
                entry = NotebookEntry(
                    universe_uuid=universe_uuid,
                    key=key,
                    version=new_version,
                    title=title,
                    summary=summary,
                    details=details,
                    kind=kind,
                    confidence=confidence,
                    expected_information=expected_information,
                    priority=priority,
                    status=status,
                    discovered_from=discovered_from,
                    relationship_type=relationship_type,
                    run_id=run_id
                )
                self.session.add(entry)
                self.session.commit()
                self.session.refresh(entry)
                return entry

        # 3. Otherwise, create a brand new entry
        entry = NotebookEntry(
            universe_uuid=universe_uuid,
            key=key,
            version=1,
            title=title,
            summary=summary,
            details=details,
            kind=kind,
            confidence=confidence,
            expected_information=expected_information,
            priority=priority,
            status=status,
            discovered_from=discovered_from,
            relationship_type=relationship_type,
            run_id=run_id
        )
        self.session.add(entry)
        self.session.commit()
        self.session.refresh(entry)
        return entry


    # --- Source Library Management ---

    def get_sources(self, universe_uuid: str) -> list[ResearchSource]:
        """Returns all sources for a world."""
        statement = (
            select(ResearchSource)
            .where(ResearchSource.universe_uuid == universe_uuid)
        )
        return self.session.exec(statement).all()

    def get_sources_index_str(self, universe_uuid: str, limit: int = 50) -> str:
        """Generates a concise list of useful sources for the agent's context."""
        sources = self.get_sources(universe_uuid)
        if not sources:
            return "No curated sources saved."

        display_sources = sources[:limit]
        lines = [
            f"[{s.id}] {s.title or s.url} (Reliability: {s.reliability or 'Unknown'})"
            for s in display_sources
        ]

        result = "USEFUL SOURCES:\n" + "\n".join(lines)
        if len(sources) > limit:
            result += f"\n(... and {len(sources) - limit} more. Use manageSource to interact with sources ...)"
        return result


    def upsert_source(
        self,
        universe_uuid: str,
        url: str,
        title: Optional[str] = None,
        reason_saved: Optional[str] = None,
        coverage: Optional[str] = None,
        reliability: Optional[str] = None,
        extraction_status: str = "UNREAD",
        strengths: Optional[str] = None,
        weaknesses: Optional[str] = None,
        source_id: Optional[int] = None
    ) -> ResearchSource:
        """Creates or updates a research source with strengths, weaknesses, and relationship metadata."""
        if source_id:
            source = self.session.get(ResearchSource, source_id)
            if source:
                source.title = title
                source.reason_saved = reason_saved
                source.coverage = coverage
                source.reliability = reliability
                source.extraction_status = extraction_status
                if strengths is not None:
                    source.strengths = strengths
                if weaknesses is not None:
                    source.weaknesses = weaknesses
                self.session.add(source)
                self.session.commit()
                self.session.refresh(source)
                return source

        source = ResearchSource(
            universe_uuid=universe_uuid,
            url=url,
            title=title,
            reason_saved=reason_saved,
            coverage=coverage,
            reliability=reliability,
            extraction_status=extraction_status,
            strengths=strengths,
            weaknesses=weaknesses
        )
        self.session.add(source)
        self.session.commit()
        self.session.refresh(source)
        return source

    def upsert_workspace_claim(self, run_id: str, universe_id: int, claim_data: dict) -> NotebookClaim:
        """Upserts a working knowledge claim for a run."""
        from app.db.notebook_schema import NotebookClaim
        statement = select(NotebookClaim).where(
            NotebookClaim.universe_id == universe_id,
            NotebookClaim.subject == claim_data.get("subject"),
            NotebookClaim.predicate == claim_data.get("predicate"),
            NotebookClaim.object_val == claim_data.get("object_val")
        )
        existing = self.session.exec(statement).first()
        if existing:
            existing.context = claim_data.get("context", existing.context)
            self.session.add(existing)
            self.session.commit()
            self.session.refresh(existing)
            return existing

        claim = NotebookClaim(
            universe_uuid=claim_data.get("universe_uuid", ""),
            universe_id=universe_id,
            subject=claim_data.get("subject", ""),
            predicate=claim_data.get("predicate", ""),
            object_val=claim_data.get("object_val", ""),
            context=claim_data.get("context")
        )
        self.session.add(claim)
        self.session.commit()
        self.session.refresh(claim)
        return claim

    def get_working_kg(self, run_id: str, universe_id: int) -> list[NotebookClaim]:
        """Returns working claims for a universe."""
        from app.db.notebook_schema import NotebookClaim
        statement = select(NotebookClaim).where(NotebookClaim.universe_id == universe_id)
        return self.session.exec(statement).all()

    def get_full_workspace_index(self, universe_uuid: str, limit: int = 50) -> str:
        """Returns full workspace index including notebook notes and useful sources."""
        n_idx = self.get_notebook_index_str(universe_uuid, limit=limit)
        s_idx = self.get_sources_index_str(universe_uuid, limit=limit)
        v_idx = self.get_visited_urls_index_str(universe_uuid, limit=limit)
        return f"{n_idx}\n\n{s_idx}\n\n{v_idx}"

    # --- Visited & Blocked URLs Tracking ---

    def log_visited_url(self, universe_uuid: str, url: str, status: str = "VISITED", error_message: Optional[str] = None):
        existing = self.session.exec(
            select(VisitedUrl).where(
                VisitedUrl.universe_uuid == universe_uuid,
                VisitedUrl.url == url
            )
        ).first()
        if existing:
            existing.status = status
            existing.error_message = error_message
            self.session.add(existing)
        else:
            vu = VisitedUrl(universe_uuid=universe_uuid, url=url, status=status, error_message=error_message)
            self.session.add(vu)
        self.session.commit()

    def get_visited_urls(self, universe_uuid: str) -> list[VisitedUrl]:
        return self.session.exec(
            select(VisitedUrl).where(VisitedUrl.universe_uuid == universe_uuid)
        ).all()

    def get_visited_urls_index_str(self, universe_uuid: str, limit: int = 30) -> str:
        items = self.get_visited_urls(universe_uuid)
        if not items:
            return "No URLs visited yet."
        display = items[-limit:]
        lines = [f"- [{v.status}] {v.url}" + (f" ({v.error_message})" if v.error_message else "") for v in display]
        return "VISITED & BLOCKED URLS:\n" + "\n".join(lines)


