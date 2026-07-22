from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, select

from app.db.notebook_schema import (
    NotebookEntry,
    ResearchSource,
    WorldDomainCache,
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

    def get_notebook_entry(self, entry_id: int) -> Optional[NotebookEntry]:
        """Returns a full notebook entry."""
        return self.session.get(NotebookEntry, entry_id)

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
        entry_id: Optional[int] = None
    ) -> NotebookEntry:
        """Creates or updates a notebook entry."""
        if entry_id:
            entry = self.session.get(NotebookEntry, entry_id)
            if entry:
                entry.title = title
                entry.summary = summary
                entry.details = details
                entry.kind = kind
                entry.status = status
                entry.priority = priority
                entry.run_id = run_id
                entry.updated_at = datetime.now(timezone.utc)
                self.session.add(entry)
                self.session.commit()
                self.session.refresh(entry)
                return entry

        entry = NotebookEntry(
            universe_uuid=universe_uuid,
            title=title,
            summary=summary,
            details=details,
            kind=kind,
            status=status,
            priority=priority,
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
        source_id: Optional[int] = None
    ) -> ResearchSource:
        """Creates or updates a research source."""
        if source_id:
            source = self.session.get(ResearchSource, source_id)
            if source:
                source.title = title
                source.reason_saved = reason_saved
                source.coverage = coverage
                source.reliability = reliability
                source.extraction_status = extraction_status
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
            extraction_status=extraction_status
        )
        self.session.add(source)
        self.session.commit()
        self.session.refresh(source)
        return source

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


