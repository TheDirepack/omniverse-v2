# TEMPORARY diagnostic capture for the acquisition pipeline. This is a raw,
# unredacted, possibly-truncated dump intended only for debugging a single
# research run. It writes JSONL to a dedicated file so it never pollutes the
# normal redacted/truncated event logs. Remove this module before release.

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

_FILE = Path(__file__).resolve().parents[2] / "data" / "pipeline-debug.jsonl"

# Hard ceiling so an experiment cannot fill the disk. The normal logger caps
# individual events; this truncates large string fields *before* serialization
# so each JSON record stays valid even for very large pages.
_MAX_RECORD_BYTES = 64_000_000
_MAX_FIELD_CHARS = 20_000_000


def _truncate(value: object) -> object:
    if isinstance(value, str):
        if len(value) > _MAX_FIELD_CHARS:
            return value[: _MAX_FIELD_CHARS] + "...[DEBUG_TRUNCATED]"
        return value
    if isinstance(value, bytes):
        try:
            text = value.decode("utf-8", errors="replace")
        except Exception:
            return value.hex()
        if len(text) > _MAX_FIELD_CHARS:
            return text[: _MAX_FIELD_CHARS] + "...[DEBUG_TRUNCATED]"
        return text
    if isinstance(value, (list, tuple)):
        return [_truncate(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _truncate(item) for key, item in value.items()}
    return value


def capture(**fields: object) -> None:
    """Append one raw pipeline record to the temporary debug file."""
    record = {"ts": datetime.now(timezone.utc).isoformat(), **_truncate(fields)}
    try:
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    except Exception:
        return
    if len(line) > _MAX_RECORD_BYTES:
        # Never emit a truncated, invalid JSON line. Drop the oversized record
        # instead so the file stays parseable. Field-level truncation above
        # already keeps most records well under the ceiling.
        return
    try:
        _FILE.parent.mkdir(parents=True, exist_ok=True)
        with _FILE.open("ab") as handle:
            handle.write(line + b"\n")
    except OSError:
        return
