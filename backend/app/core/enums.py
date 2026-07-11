from enum import Enum


class RunPhase(str, Enum):
    """High-level phases and statuses of the Omniverse pipeline."""
    # Lifecycle
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    ABORT_REQUESTED = "ABORT_REQUESTED"



    # Workflow phases
    RESEARCH = "RESEARCH"
    RESEARCHING = "RESEARCHING"
    FACILITATION = "FACILITATION"
    FACILITATING = "FACILITATING"
    DB_INTEGRATION = "DB_INTEGRATION"
    INTEGRATING = "INTEGRATING"
    SUMMARY = "SUMMARY"
    SUMMARIZING = "SUMMARIZING"
    ARCHITECTURE = "ARCHITECTURE"
    RE_ARCHITECTURE = "RE_ARCHITECTURE"
    EXTRAPOLATION = "EXTRAPOLATION"
    FINISHED = "FINISHED"

    def __str__(self) -> str:
        return self.value

# Alias RunStatus to RunPhase to prevent breaking existing imports
RunStatus = RunPhase
