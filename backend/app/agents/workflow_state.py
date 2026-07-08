from typing import Any, TypedDict
from app.core.domain import ResearchTarget

class OmniverseState(TypedDict):
    run_id: str
    target_worlds: list[ResearchTarget]
    focused_features: list[str] | None  # Targets for focused search
    is_focused_search: bool  # Whether this is a focused search run
    research_results: list[Any]
    verified_worlds: list[str]
    current_tier_system: str | None
    system_stable: bool
    anomalies: list[str]
    generated_theories: list[Any]
    active_task: str
    errors: list[str]
    architecture_retries: int
    architecture_attempts: int
