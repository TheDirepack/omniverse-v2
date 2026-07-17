import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.agent_event_types import AgentEventType
from app.core.context import get_current_universe

LOG_FILE: Path | None = None
agent_sys_logger: logging.Logger = logging.getLogger("agent_system")


def configure(
    log_dir: str | None = None,
    log_file: str | None = None,
    log_level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
):
    global LOG_FILE

    if log_file:
        log_path = Path(log_file)
    elif log_dir:
        log_path = Path(log_dir) / "agents.log"
    else:
        log_path = Path(__file__).parent.parent.parent / "logs" / "agents.log"

    log_path.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE = log_path

    agent_sys_logger.setLevel(log_level)
    agent_sys_logger.handlers.clear()

    handler = RotatingFileHandler(
        LOG_FILE, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    agent_sys_logger.addHandler(handler)


# Auto-configure from environment variables at import time
env_log_dir = os.environ.get("APP_LOG_DIR")
env_log_file = os.environ.get("APP_LOG_FILE")
env_log_level = os.environ.get("APP_LOG_LEVEL", "INFO").upper()
configure(
    log_dir=env_log_dir or None,
    log_file=env_log_file or None,
    log_level=getattr(logging, env_log_level, logging.INFO),
)


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

        event_type_str = event_type.value if isinstance(event_type, AgentEventType) else str(event_type)

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        world_name = get_current_universe() or "unknown"

        log_line = (
            f"[{timestamp}] [{agent}] [{model}] [{key_id}] "
            f"[{world_name}] [{event_type_str}] {content}"
        )

        agent_sys_logger.info(log_line)


agent_logger = AgentLogger()
