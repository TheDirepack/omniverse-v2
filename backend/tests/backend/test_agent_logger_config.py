"""Tests for agent_logger configuration (no DB needed)."""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from unittest.mock import patch


from app.core import agent_logger as al


class TestConfigure:
    def test_configure_with_log_file(self, tmp_path):
        log_file = tmp_path / "agent_logger.log"
        al.configure(log_file=str(log_file))
        assert str(al.LOG_FILE) == str(log_file)
        assert len(al.agent_sys_logger.handlers) == 1
        h = al.agent_sys_logger.handlers[0]
        assert isinstance(h, RotatingFileHandler)
        assert h.baseFilename == str(al.LOG_FILE)

    def test_configure_with_log_dir(self, tmp_path):
        al.configure(log_dir=str(tmp_path))
        assert str(al.LOG_FILE) == str(tmp_path / "agents.log")

    def test_configure_default_path(self):
        al.configure()
        expected = Path(__file__).parent.parent.parent / "logs" / "agents.log"
        assert al.LOG_FILE == expected

    def test_configure_respects_log_level(self, tmp_path):
        log_file = tmp_path / "test_log_level.log"
        al.configure(log_file=str(log_file), log_level=logging.DEBUG)
        assert al.agent_sys_logger.level == logging.DEBUG

        al.configure(log_file=str(log_file), log_level=logging.WARNING)
        assert al.agent_sys_logger.level == logging.WARNING

    def test_configure_clears_previous_handlers(self, tmp_path):
        al.configure(log_file=str(tmp_path / "clear_1.log"))
        al.configure(log_file=str(tmp_path / "clear_2.log"))
        assert len(al.agent_sys_logger.handlers) == 1

    def test_configure_rotation_defaults(self, tmp_path):
        al.configure(log_file=str(tmp_path / "rotation.log"))
        h = al.agent_sys_logger.handlers[0]
        assert h.maxBytes == 10 * 1024 * 1024
        assert h.backupCount == 5

    def test_configure_custom_rotation(self, tmp_path):
        log_file = tmp_path / "custom_rotation.log"
        al.configure(log_file=str(log_file), max_bytes=1024, backup_count=2)
        h = al.agent_sys_logger.handlers[0]
        assert h.maxBytes == 1024
        assert h.backupCount == 2

    def test_configure_creates_parent_dir(self, tmp_path):
        al.configure(log_file=str(tmp_path / "nested" / "agents.log"))
        assert al.LOG_FILE.parent.exists()


class TestConfigureEnvVars:
    def test_env_log_level(self):
        with patch.dict(os.environ, {"APP_LOG_LEVEL": "DEBUG"}, clear=True):
            import importlib
            importlib.reload(al)
            assert al.agent_sys_logger.level == logging.DEBUG

    def test_env_log_dir(self):
        with patch.dict(os.environ, {"APP_LOG_DIR": "/tmp/opencode_test"}, clear=True):
            import importlib
            importlib.reload(al)
            assert str(al.LOG_FILE) == "/tmp/opencode_test/agents.log"

    def test_env_log_file(self):
        with patch.dict(os.environ, {"APP_LOG_FILE": "/tmp/custom_path.log"}, clear=True):
            import importlib
            importlib.reload(al)
            assert str(al.LOG_FILE) == "/tmp/custom_path.log"

    def test_env_log_file_overrides_log_dir(self):
        with patch.dict(os.environ, {"APP_LOG_DIR": "/tmp/some_dir", "APP_LOG_FILE": "/tmp/override.log"}, clear=True):
            import importlib
            importlib.reload(al)
            assert str(al.LOG_FILE) == "/tmp/override.log"

    def test_default_log_level_info(self):
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            importlib.reload(al)
            assert al.agent_sys_logger.level == logging.INFO


class TestAgentLogger:
    def test_log_writes_to_file(self, tmp_path):
        al.configure(log_file=str(tmp_path / "agents.log"))
        with patch.object(al.AgentLogger, "_is_logging_enabled", return_value=True):
            al.agent_logger.log("TestAgent", "INFO", "hello world")

        lines = (tmp_path / "agents.log").read_text().strip().split("\n")
        assert len(lines) >= 1
        assert "[TestAgent]" in lines[-1]
        assert "[INFO]" in lines[-1]
        assert "hello world" in lines[-1]

    def test_log_skipped_when_disabled(self, tmp_path):
        log_file = tmp_path / "test_disabled.log"
        al.configure(log_file=str(log_file))
        with patch.object(al.AgentLogger, "_is_logging_enabled", return_value=False):
            al.agent_logger.log("TestAgent", "INFO", "should not appear")
        content = log_file.read_text().strip()
        assert content == ""
