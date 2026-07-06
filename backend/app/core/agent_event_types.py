from enum import Enum

class AgentEventType(str, Enum):
    """Canonical event types for agent logging."""
    THOUGHT = "THOUGHT"
    TOOL_REQ = "TOOL_REQ"
    TOOL_RES = "TOOL_RES"
    PROMPT = "PROMPT"
    MODEL_CALL = "MODEL_CALL"
    ERROR = "ERROR"
    FAILED = "FAILED"
    INFO = "INFO"
    WARNING = "WARNING"
    COMPLETED = "COMPLETED"
    IN_PROGRESS = "IN_PROGRESS"
