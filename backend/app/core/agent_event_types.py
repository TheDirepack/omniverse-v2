from enum import Enum

from app.core.enums import RunStatus


class AgentEventType(str, Enum):
    """Canonical event types for agent logging."""

    THOUGHT = "THOUGHT"
    TOOL_REQ = "TOOL_REQ"
    TOOL_RES = "TOOL_RES"
    PROMPT = "PROMPT"
    MODEL_CALL = "MODEL_CALL"
    ERROR = "ERROR"
    FAILED = RunStatus.FAILED
    INFO = "INFO"
    WARNING = "WARNING"
    COMPLETED = RunStatus.COMPLETED
    IN_PROGRESS = "IN_PROGRESS"
    STEP = "STEP"

