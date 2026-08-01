# Logging validation errors are operator-facing and intentionally explicit.
# ruff: noqa: TRY003

from __future__ import annotations

import json
import math
import os
import re
import threading
import uuid
from contextvars import ContextVar, Token
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.v2.models import RuntimeSetting, utcnow

DEFAULT_LOG_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "logging.v1"
MAX_FIELD_CHARACTERS = 4096
MAX_EVENT_BYTES = 65_536
MAX_COLLECTION_ITEMS = 100
MAX_DEPTH = 8
_LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
_SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "credential",
    "credentials",
    "password",
    "passwd",
    "privatekey",
    "secret",
    "setcookie",
    "token",
    "apikey",
    "accesskey",
}
_AUTH_PATTERN = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]+")
_API_KEY_PATTERN = re.compile(r"(?i)\b(api[_-]?key)\s*[:=]\s*[^\s,;]+")
_URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_CORRELATION_FIELDS = (
    "request_id",
    "run_id",
    "target_id",
    "step_id",
    "world_id",
    "model_id",
    "provider_id",
)
_REQUEST_ID: ContextVar[str | None] = ContextVar("v2_request_id", default=None)


def bind_request_id(request_id: str) -> Token[str | None]:
    return _REQUEST_ID.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    _REQUEST_ID.reset(token)


def _is_sensitive_key(value: object) -> bool:
    normalized = _normalized_key(value)
    return normalized in _SENSITIVE_KEYS or normalized.endswith(
        ("secret", "token", "password", "passwd", "apikey", "accesskey", "credential")
    )


@dataclass(frozen=True, slots=True)
class LoggingSettings:
    enabled: bool = True
    folder: str = "logs"
    server_level: str = "INFO"
    agent_level: str = "INFO"
    server_max_bytes: int = 5_000_000
    agent_max_bytes: int = 5_000_000
    server_backup_count: int = 5
    agent_backup_count: int = 5

    def __post_init__(self) -> None:
        for name in ("server_level", "agent_level"):
            value = getattr(self, name).upper()
            if value not in _LEVELS:
                raise ValueError(f"{name} must be one of {sorted(_LEVELS)}")
            object.__setattr__(self, name, value)
        if not isinstance(self.enabled, bool):
            raise TypeError("enabled must be a boolean")
        if not isinstance(self.folder, str) or not self.folder:
            raise ValueError("folder must be a non-empty relative path")
        for name in ("server_max_bytes", "agent_max_bytes"):
            value = getattr(self, name)
            if not isinstance(value, int) or not 1024 <= value <= 100_000_000:
                raise ValueError(f"{name} must be between 1024 and 100000000")
        for name in ("server_backup_count", "agent_backup_count"):
            value = getattr(self, name)
            if not isinstance(value, int) or not 0 <= value <= 100:
                raise ValueError(f"{name} must be between 0 and 100")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> LoggingSettings:
        return cls(**value)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalized_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _redact_url(match: re.Match[str]) -> str:
    raw = match.group(0)
    trailing = ""
    while raw and raw[-1] in ").,;]}":
        trailing = raw[-1] + trailing
        raw = raw[:-1]
    try:
        parsed = urlsplit(raw)
        hostname = parsed.hostname or ""
        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        netloc = hostname
        if parsed.port is not None:
            netloc += f":{parsed.port}"
        query = urlencode(
            [
                (
                    key,
                    "[REDACTED]" if _is_sensitive_key(key) else value,
                )
                for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            ]
        )
        return (
            urlunsplit((parsed.scheme, netloc, parsed.path, query, parsed.fragment))
            + trailing
        )
    except ValueError:
        return "[REDACTED_URL]" + trailing


def _redact_text(value: object) -> str:
    text = str(value)
    text = _AUTH_PATTERN.sub(lambda match: f"{match.group(1)} [REDACTED]", text)
    text = _API_KEY_PATTERN.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    text = _URL_PATTERN.sub(_redact_url, text)
    if len(text) > MAX_FIELD_CHARACTERS:
        return text[: MAX_FIELD_CHARACTERS - 11] + "...[TRUNCATED]"
    return text


def redact(value: Any, *, _depth: int = 0) -> Any:
    if _depth >= MAX_DEPTH:
        return "[TRUNCATED]"
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= MAX_COLLECTION_ITEMS:
                result["[truncated]"] = True
                break
            safe_key = _redact_text(key)
            result[safe_key] = (
                "[REDACTED]"
                if _is_sensitive_key(key)
                else redact(item, _depth=_depth + 1)
            )
        return result
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        result = [
            redact(item, _depth=_depth + 1) for item in items[:MAX_COLLECTION_ITEMS]
        ]
        if len(items) > MAX_COLLECTION_ITEMS:
            result.append("[TRUNCATED]")
        return result
    if isinstance(value, float) and not math.isfinite(value):
        return "[NON_FINITE]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _redact_text(value)


class _RotatingJsonlStream:
    def __init__(self, path: Path, max_bytes: int, backup_count: int) -> None:
        self.path = path
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.file: TextIO = self._open()

    def _open(self) -> TextIO:
        flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self.path, flags, 0o600)
        os.fchmod(descriptor, 0o600)
        return os.fdopen(descriptor, "a", encoding="utf-8")

    def write(self, line: str) -> None:
        encoded_size = len(line.encode("utf-8")) + 1
        self.file.flush()
        if (
            self.path.stat().st_size
            and self.path.stat().st_size + encoded_size > self.max_bytes
        ):
            self._rotate()
        self.file.write(line + "\n")
        self.file.flush()

    def _rotate(self) -> None:
        self.file.close()
        if self.backup_count:
            oldest = self.path.with_name(f"{self.path.name}.{self.backup_count}")
            oldest.unlink(missing_ok=True)
            for index in range(self.backup_count - 1, 0, -1):
                source = self.path.with_name(f"{self.path.name}.{index}")
                if source.exists():
                    source.replace(self.path.with_name(f"{self.path.name}.{index + 1}"))
            self.path.replace(self.path.with_name(f"{self.path.name}.1"))
            self.path.with_name(f"{self.path.name}.1").chmod(0o600)
        else:
            self.path.unlink(missing_ok=True)
        self.file = self._open()

    def close(self) -> None:
        if not self.file.closed:
            self.file.flush()
            self.file.close()

    @property
    def active(self) -> bool:
        return not self.file.closed


class V2ServerLogger:
    def __init__(self, root: Path | str = DEFAULT_LOG_ROOT) -> None:
        self._root = Path(root).expanduser().resolve()
        self._lock = threading.RLock()
        self._settings = LoggingSettings(enabled=False)
        self._folder = self._resolve_folder(self._settings.folder)
        self._streams: dict[str, _RotatingJsonlStream] = {}
        self._last_error: str | None = None

    @property
    def settings(self) -> LoggingSettings:
        return self._settings

    def _resolve_folder(self, folder: str) -> Path:
        if "\0" in folder:
            raise ValueError("logging folder contains NUL")
        relative = Path(folder)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("logging folder must be relative without traversal")
        candidate = (self._root / relative).resolve()
        if not candidate.is_relative_to(self._root):
            raise ValueError("logging folder must resolve under logging root")
        return candidate

    def reconfigure(self, settings: LoggingSettings) -> None:
        try:
            folder = self._resolve_folder(settings.folder)
        except ValueError as error:
            with self._lock:
                self._last_error = _redact_text(error)
            raise
        with self._lock:
            replacements: dict[str, _RotatingJsonlStream] = {}
            try:
                if settings.enabled:
                    self._root.mkdir(parents=True, exist_ok=True, mode=0o700)
                    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
                    folder.chmod(0o700)
                    replacements["server"] = _RotatingJsonlStream(
                        folder / "server.jsonl",
                        settings.server_max_bytes,
                        settings.server_backup_count,
                    )
                    replacements["agent"] = _RotatingJsonlStream(
                        folder / "agent.jsonl",
                        settings.agent_max_bytes,
                        settings.agent_backup_count,
                    )
                    replacements["remote-server"] = _RotatingJsonlStream(
                        folder / "remote-server.jsonl",
                        settings.server_max_bytes,
                        settings.server_backup_count,
                    )
            except Exception as error:
                for stream in replacements.values():
                    stream.close()
                self._last_error = _redact_text(error)
                raise
            old_streams = self._streams
            self._streams = replacements
            self._settings = settings
            self._folder = folder
            self._last_error = None
            for stream in old_streams.values():
                stream.close()

    def log_event(
        self,
        stream: str,
        level: str,
        event_type: str,
        component: str,
        message: str,
        *,
        data: Any = None,
        **correlation: Any,
    ) -> None:
        if stream not in {"server", "agent", "remote-server"}:
            raise ValueError("stream must be server, agent, or remote-server")
        normalized_level = level.upper()
        if normalized_level not in _LEVELS:
            raise ValueError(f"unknown logging level: {level}")
        with self._lock:
            target = self._streams.get(stream)
            configured_level = (
                self._settings.server_level
                if stream in {"server", "remote-server"}
                else self._settings.agent_level
            )
            if target is None or _LEVELS[normalized_level] < _LEVELS[configured_level]:
                return
            request_id = correlation.get("request_id") or _REQUEST_ID.get()
            effective_correlation = {
                **correlation,
                **({"request_id": request_id} if request_id is not None else {}),
            }
            event = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "schema_version": SCHEMA_VERSION,
                "event_id": str(uuid.uuid4()),
                "stream": stream,
                "level": normalized_level,
                "event_type": _redact_text(event_type),
                "component": _redact_text(component),
                "message": _redact_text(message),
                **{
                    name: (
                        _redact_text(effective_correlation[name])
                        if effective_correlation.get(name) is not None
                        else None
                    )
                    for name in _CORRELATION_FIELDS
                },
                "data": redact(data if data is not None else {}),
            }
            line = json.dumps(
                event, ensure_ascii=False, allow_nan=False, separators=(",", ":")
            )
            if len(line.encode("utf-8")) + 1 > MAX_EVENT_BYTES:
                event["data"] = {"truncated": True}
                for name in (
                    "event_type",
                    "component",
                    "message",
                    *_CORRELATION_FIELDS,
                ):
                    if event[name] is not None:
                        event[name] = str(event[name])[:512]
                line = json.dumps(
                    event, ensure_ascii=False, allow_nan=False, separators=(",", ":")
                )
            try:
                target.write(line)
            except OSError as error:
                self._last_error = _redact_text(error)

    def log_access(
        self,
        method: str,
        path: str,
        status: int,
        duration_ms: float,
        client_ip: str = "",
        request_id: str = "",
    ) -> None:
        self.log_event(
            "server",
            "INFO" if status < 400 else "WARNING" if status < 500 else "ERROR",
            "http.request.completed",
            "middleware",
            f"{method} {path} completed with {status}",
            data={
                "method": method,
                "path": path,
                "status": status,
                "duration_ms": duration_ms,
                "client_ip": client_ip,
            },
            request_id=request_id,
        )

    def log_error(
        self,
        level: str,
        source: str,
        status: int,
        path: str,
        message: str,
        traceback: str = "",
    ) -> None:
        self.log_event(
            "server",
            level,
            "server.error",
            source,
            message,
            data={"status": status, "path": path, "traceback": traceback},
        )

    def log_client(
        self,
        level: str,
        source: str,
        message: str,
        url: str = "",
        user_agent: str = "",
        stack: str = "",
    ) -> None:
        self.log_event(
            "server",
            level,
            "client.event",
            source,
            message,
            data={"url": url, "user_agent": user_agent, "stack": stack},
        )

    def log_agent(
        self,
        agent_name: str,
        event_type: str,
        world_name: str = "",
        run_id: str = "",
        step_kind: str = "",
        model: str = "",
        message: str = "",
        *,
        level: str = "INFO",
        data: Any = None,
        **correlation: Any,
    ) -> None:
        merged_data = {
            **({"world_name": world_name} if world_name else {}),
            **({"step_kind": step_kind} if step_kind else {}),
            **({"model": model} if model else {}),
            **(
                data
                if isinstance(data, dict)
                else {"value": data}
                if data is not None
                else {}
            ),
        }
        self.log_event(
            "agent",
            level,
            event_type,
            agent_name,
            message,
            data=merged_data,
            run_id=run_id,
            **correlation,
        )

    def log_settings_action(self, action: str, details: dict) -> None:
        self.log_event(
            "server", "INFO", "settings.action", "settings", action, data=details
        )

    def health(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": self._settings.enabled,
                "folder": str(self._folder),
                "streams": {
                    name: name in self._streams and self._streams[name].active
                    for name in ("server", "agent", "remote-server")
                },
                "last_error": self._last_error,
            }

    def close(self) -> None:
        with self._lock:
            streams = self._streams
            self._streams = {}
            for stream in streams.values():
                stream.close()

    def _path_for(self, log_type: str) -> Path:
        aliases = {"access": "server", "error": "server", "client": "server"}
        stream = aliases.get(log_type, log_type)
        if stream not in {"server", "agent", "remote-server"}:
            raise ValueError(f"unknown log type: {log_type}")
        return self._folder / f"{stream}.jsonl"

    def read_log(
        self,
        log_type: str,
        cursor: int = 0,
        limit: int = 100,
        level_filter: str = "",
        search: str = "",
    ) -> dict[str, Any]:
        path = self._path_for(log_type)
        stream_name = "agent" if log_type == "agent" else "server"
        with self._lock:
            stream = self._streams.get(stream_name)
            if stream is not None:
                stream.file.flush()
            backup_count = getattr(self._settings, f"{stream_name}_backup_count")
            paths = [
                path.with_name(f"{path.name}.{index}")
                for index in range(backup_count, 0, -1)
            ] + [path]
            existing = [candidate for candidate in paths if candidate.exists()]
            if not existing:
                return {"lines": [], "next_cursor": 0, "total_lines": 0}
            lines: list[str] = []
            total_lines = 0
            search_value = search.casefold()
            for candidate in existing:
                with candidate.open("r", encoding="utf-8", errors="replace") as handle:
                    for raw_line in handle:
                        line = raw_line.rstrip("\r\n")
                        try:
                            parsed = json.loads(line)
                        except (json.JSONDecodeError, TypeError):
                            parsed_level = "ERROR"
                        else:
                            parsed_level = (
                                str(parsed.get("level", ""))
                                if isinstance(parsed, dict)
                                else "ERROR"
                            )
                        if level_filter and parsed_level != level_filter:
                            continue
                        if search_value and search_value not in line.casefold():
                            continue
                        if cursor <= total_lines < cursor + limit:
                            lines.append(line)
                        total_lines += 1
        end = min(cursor + len(lines), total_lines)
        return {
            "lines": lines,
            "next_cursor": end,
            "total_lines": total_lines,
        }

    def clear_logs(self) -> dict[str, bool]:
        result: dict[str, bool] = {}
        with self._lock:
            for name in ("server", "agent"):
                stream = self._streams.get(name)
                try:
                    if stream is not None:
                        stream.file.seek(0)
                        stream.file.truncate()
                        stream.file.flush()
                    else:
                        self._path_for(name).write_text("", encoding="utf-8")
                        self._path_for(name).chmod(0o600)
                    result[f"{name}.jsonl"] = True
                except OSError:
                    result[f"{name}.jsonl"] = False
        return result


class LoggingSettingsService:
    def __init__(self, engine: Engine, logger: V2ServerLogger) -> None:
        self._engine = engine
        self._logger = logger
        self._settings = LoggingSettings()

    @property
    def settings(self) -> LoggingSettings:
        return self._settings

    def load_and_apply(self) -> LoggingSettings:
        with Session(self._engine) as session:
            row = session.get(RuntimeSetting, "logging")
            settings = (
                LoggingSettings.from_dict(row.value_json) if row else LoggingSettings()
            )
            if row is None:
                session.add(
                    RuntimeSetting(
                        key="logging",
                        value_json=settings.to_dict(),
                        updated_at=utcnow(),
                    )
                )
                session.commit()
        self._logger.reconfigure(settings)
        self._settings = settings
        return settings

    def update(self, settings: LoggingSettings) -> LoggingSettings:
        prior = self._settings
        applied = False
        try:
            with Session(self._engine) as session, session.begin():
                row = session.get(RuntimeSetting, "logging")
                if row is None:
                    row = RuntimeSetting(
                        key="logging", value_json={}, updated_at=utcnow()
                    )
                    session.add(row)
                row.value_json = settings.to_dict()
                row.updated_at = utcnow()
                self._logger.reconfigure(settings)
                applied = True
        except Exception:
            if applied:
                self._logger.reconfigure(prior)
            raise
        self._settings = settings
        return settings
