from typing import TypedDict, List, Any, Optional

class OmniverseState(TypedDict):
    run_id: str
    target_worlds: List[str]
    research_results: List[Any]
    verified_worlds: List[str]
    current_tier_system: Optional[str]
    system_stable: bool
    anomalies: List[str]
    generated_theories: List[Any]
    active_task: str
    errors: List[str]
    architecture_retries: int
