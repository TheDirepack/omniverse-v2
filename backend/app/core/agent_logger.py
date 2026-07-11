import logging
from datetime import datetime
from pathlib import Path

from app.core.agent_event_types import AgentEventType
from app.core.context import get_current_universe

# Define log file path relative to this file:
# backend/app/core/agent_logger.py -> backend/logs/agents.log
LOG_FILE = Path(__file__).parent.parent.parent / "logs" / "agents.log"

# Ensure directory exists
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Configure a dedicated logger for agents
agent_sys_logger = logging.getLogger("agent_system")
agent_sys_logger.setLevel(logging.INFO)
handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
# We use a simple format because the log() method handles the structured content
formatter = logging.Formatter("%(message)s")
handler.setFormatter(formatter)
agent_sys_logger.addHandler(handler)


class AgentLogger:
    @staticmethod
    def _is_logging_enabled() -> bool:
        try:
            from app.db.schema import Setting
            from app.db.settings_session import Session, settings_engine

            with Session(settings_engine) as session:
                setting = session.get(Setting, "AGENT_LOGGING")
                if setting is None:
                    return True
                return setting.value.lower() != "false"
        except Exception:
            agent_sys_logger.exception("Error checking AGENT_LOGGING setting")
            return True

    @staticmethod
    def log(
        agent: str,
        event_type: AgentEventType | str,
        content: str,
        model: str | None = "unknown",
        key_id: str | None = "unknown",
    ):
        if not AgentLogger._is_logging_enabled():
            return

        # Ensure event_type is a string for formatting
        event_type_str = str(event_type)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        world_name = get_current_universe() or "unknown"

        # [Timestamp] [Agent] [Model] [KeyID] [WorldName] [Type] Content
        log_line = (
            f"[{timestamp}] [{agent}] [{model}] [{key_id}] "
            f"[{world_name}] [{event_type_str}] {content}"
        )

        # Use the configured logger instead of direct file writing
        agent_sys_logger.info(log_line)


agent_logger = AgentLogger()
