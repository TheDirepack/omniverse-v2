from dataclasses import dataclass, field
from typing import Optional

RESEARCH_SCHEMA = """
{
  "Universe_Name": "string",
  "Source_Wikis": ["url or wiki name"],
  "Verified_Claims": [
    {
      "subject": "string",
      "context": (
          "string (The section heading or conceptual grouping, e.g. "
          "'Physical Specifications', 'Armament')"
      ),
      "predicate": "string",
      "object_val": "string",
      "reference": "url: section/line",
      "wiki_source": "page name or url",
      "confidence": "High | Medium | Low",
       "staging_ref": "integer | null (The ID from saveNotebookEntry, if applicable)"

    }
  ],
  "Knowledge_Graph": [
    {
      "Lead": "string (person, place, term, or specific detail)",
      "Reason": (
          "Why this is worth investigating further (e.g. 'mentions a secret "
          "lab', 'contradicts X', 'references unknown technology')"
      ),
      "Expected_Value": "What info we hope to find by following this lead",
      "URL": "url to follow if available",
      "Priority": "1-10 (10 highest)",
      "Information_Gain": "High | Medium | Low",
      "Prerequisites": ["Other leads that must be resolved first"],
      "Status": "Pending | Visited | Blocked",
      "Attempts": "integer",
      "Estimated_Cost": "Low | Medium | High"
    }
  ],
  "Missing_Info": ["string"],
  "Provisional_Conclusions": [
    {
      "Conclusion": "string",
      "Reasoning": "string",
      "Confidence": "Low | Medium | High",
      "Verification_Need": "string"
    }
  ]
}
"""

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

    def primary_name(self) -> str:
        """The basic identifier of the world."""
        return self.name

    def display_name(self) -> str:
        """Human-readable name, accounting for overlap with era/continuity."""
        if (
            (self.era and self.name == self.era)
            or (self.continuity and self.name == self.continuity)
        ):
            return self.franchise or self.name
        return self.name

    def canonical_key(self) -> str:
        """A unique string key for caching and indexing."""
        return f"{self.franchise or 'unknown'}:{self.name}"

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
