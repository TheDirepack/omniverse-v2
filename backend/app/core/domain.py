from dataclasses import dataclass, field
from typing import Optional

@dataclass(frozen=True)
class ResearchTarget:
    """
    An immutable domain object representing a world targeted for research.
    Preserves identity (UUID) and context (Name, Franchise, etc.) throughout 
    the workflow to avoid repeated database lookups.
    """
    uuid: str
    name: str
    franchise: Optional[str] = None
    continuity: Optional[str] = None
    era: Optional[str] = None
    slug: Optional[str] = None
    parent_id: Optional[int] = None

@dataclass
class ResearchWorkspace:
    """
    Represents a stateful work area for a specific research run.
    Tracks provenance, working notes, and transient knowledge.
    """
    run_id: str
    notebook: str = ""
    working_kg: dict = field(default_factory=dict)
    claims_dirty: bool = False
    theories_dirty: bool = False
    graph_dirty: bool = False
    revision_number: int = 0
