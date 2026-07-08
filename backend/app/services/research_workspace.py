from typing import List, Optional
from sqlmodel import Session, select
from app.db.unconfirmed_session import unconfirmed_engine
from app.db.unconfirmed_schema import (
    UnconfirmedClaim,
    NotebookEntry, 
    ResearchSource, 
    TimelineEntry, 
    TimelineParticipant, 
    TimelineLocation, 
    TimelineSource, 
    TimelineClaim
)
from datetime import datetime

class WorkspaceService:
    def __init__(self, session: Optional[Session] = None):
        self.session = session or Session(unconfirmed_engine)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            self.session.close()

    # --- Notebook Management ---

    def get_notebook_index(self, universe_uuid: str) -> List[NotebookEntry]:
        """Returns a list of notebook entries (summaries) for a world."""
        statement = select(NotebookEntry).where(NotebookEntry.universe_uuid == universe_uuid).order_by(NotebookEntry.priority)
        return self.session.exec(statement).all()

    def get_notebook_index_str(self, universe_uuid: str) -> str:
        """Generates a concise list of notebook entries for the agent's context."""
        entries = self.get_notebook_index(universe_uuid)
        if not entries:
            return "No active research notes."
        lines = [f"[{e.id}] {e.title} (Status: {e.status}, Priority: {e.priority})" for e in entries]
        return "RESEARCH NOTES:\n" + "\n".join(lines)

    def get_notebook_content(self, run_id: str, universe_uuid: str) -> str:
        """Returns the concatenated summaries of all notebook entries for a run."""
        statement = select(NotebookEntry.summary).where(
            NotebookEntry.run_id == run_id,
            NotebookEntry.universe_uuid == universe_uuid
        ).order_by(NotebookEntry.priority)
        summaries = self.session.exec(statement).all()
        return "\n".join(filter(None, summaries))

    def get_notebook_entry(self, entry_id: int) -> Optional[NotebookEntry]:
        """Returns a full notebook entry."""
        return self.session.get(NotebookEntry, entry_id)

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
                entry.updated_at = datetime.utcnow()
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

    def get_sources(self, universe_uuid: str) -> List[ResearchSource]:
        """Returns all sources for a world."""
        statement = select(ResearchSource).where(ResearchSource.universe_uuid == universe_uuid)
        return self.session.exec(statement).all()

    def get_sources_index_str(self, universe_uuid: str) -> str:
        """Generates a concise list of useful sources for the agent's context."""
        sources = self.get_sources(universe_uuid)
        if not sources:
            return "No curated sources saved."
        lines = [f"[{s.id}] {s.title or s.url} (Reliability: {s.reliability or 'Unknown'})" for s in sources]
        return "USEFUL SOURCES:\n" + "\n".join(lines)

    def upsert_workspace_claim(self, run_id: str, universe_id: int, claim_data: dict) -> UnconfirmedClaim:
        """Saves a claim to the run-isolated workspace."""
        # Check if claim already exists for this run and universe
        statement = select(UnconfirmedClaim).where(
            UnconfirmedClaim.run_id == run_id,
            UnconfirmedClaim.universe_id == universe_id,
            UnconfirmedClaim.subject == claim_data.get("subject"),
            UnconfirmedClaim.predicate == claim_data.get("predicate"),
            UnconfirmedClaim.object_val == claim_data.get("object_val")
        )
        existing = self.session.exec(statement).first()
        
        if existing:
            for key, value in claim_data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            self.session.add(existing)
            self.session.commit()
            self.session.refresh(existing)
            return existing
        
        claim = UnconfirmedClaim(
            run_id=run_id,
            universe_id=universe_id,
            **claim_data
        )
        self.session.add(claim)
        self.session.commit()
        self.session.refresh(claim)
        return claim

    def get_working_kg(self, run_id: str, universe_id: int) -> List[UnconfirmedClaim]:
        """Returns all claims for a specific run and universe."""
        statement = select(UnconfirmedClaim).where(
            UnconfirmedClaim.run_id == run_id,
            UnconfirmedClaim.universe_id == universe_id
        )
        return self.session.exec(statement).all()

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

    # --- Timeline Management ---

    def get_timeline(self, universe_uuid: str) -> List[TimelineEntry]:
        """Returns the chronology of events for a world."""
        statement = select(TimelineEntry).where(TimelineEntry.universe_uuid == universe_uuid).order_by(TimelineEntry.date)
        return self.session.exec(statement).all()

    def get_timeline_index_str(self, universe_uuid: str) -> str:
        """Generates a concise list of timeline events for the agent's context."""
        events = self.get_timeline(universe_uuid)
        if not events:
            return "No timeline events recorded."
        lines = [f"[{e.id}] {e.title} (Era: {e.era or 'Unknown'})" for e in events]
        return "TIMELINE EVENTS:\n" + "\n".join(lines)

    def get_full_workspace_index(self, universe_uuid: str) -> str:
        """Aggregates all indices into a single context block."""
        return (
            f"{self.get_notebook_index_str(universe_uuid)}\n\n"
            f"{self.get_sources_index_str(universe_uuid)}\n\n"
            f"{self.get_timeline_index_str(universe_uuid)}"
        )

    def create_timeline_event(
        self, 
        universe_uuid: str, 
        title: str, 
        date: Optional[str] = None, 
        era: Optional[str] = None, 
        summary: Optional[str] = None, 
        description: Optional[str] = None, 
        importance: int = 1, 
        confidence: float = 1.0
    ) -> TimelineEntry:
        """Creates a new timeline event."""
        event = TimelineEntry(
            universe_uuid=universe_uuid,
            title=title,
            date=date,
            era=era,
            summary=summary,
            description=description,
            importance=importance,
            confidence=confidence
        )
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return event

    def add_timeline_participant(self, timeline_id: int, entity_id: int, role: Optional[str] = None):
        participant = TimelineParticipant(timeline_id=timeline_id, entity_id=entity_id, role=role)
        self.session.add(participant)
        self.session.commit()

    def add_timeline_location(self, timeline_id: int, location_id: int):
        location = TimelineLocation(timeline_id=timeline_id, location_id=location_id)
        self.session.add(location)
        self.session.commit()

    def add_timeline_source(self, timeline_id: int, source_id: int):
        tsource = TimelineSource(timeline_id=timeline_id, source_id=source_id)
        self.session.add(tsource)
        self.session.commit()

    def add_timeline_claim(self, timeline_id: int, claim_id: int):
        tclaim = TimelineClaim(timeline_id=timeline_id, claim_id=claim_id)
        self.session.add(tclaim)
        self.session.commit()
