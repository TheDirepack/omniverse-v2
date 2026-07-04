import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from app.core.context import get_current_universe

# Define log file path relative to this file: backend/app/core/agent_logger.py -> backend/logs/agents.log
LOG_FILE = Path(__file__).parent.parent.parent / "logs" / "agents.log"

# Ensure directory exists
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

class AgentLogger:
    @staticmethod
    def _is_logging_enabled() -> bool:
        try:
            from app.db.session import Session, engine
            from app.db.schema import Setting
            with Session(engine) as session:
                setting = session.get(Setting, "AGENT_LOGGING")
                if setting is None:
                    return True
                return setting.value.lower() != "false"
        except Exception:
            return True

    @staticmethod
    def log(
        agent: str,
        event_type: str,
        content: str,
        model: Optional[str] = "unknown",
        key_id: Optional[str] = "unknown",
    ):
        if not AgentLogger._is_logging_enabled():
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        world_name = get_current_universe() or "unknown"
        
        # [Timestamp] [Agent] [Model] [KeyID] [WorldName] [Type] Content
        log_line = f"[{timestamp}] [{agent}] [{model}] [{key_id}] [{world_name}] [{event_type}] {content}\n"
        
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line)

agent_logger = AgentLogger()
