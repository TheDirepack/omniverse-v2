import logging
from typing import Any

from fastapi import Request


def get_structured_logger(name: str, request: Request | None = None) -> logging.LoggerAdapter:
    """Get a logger adapter with contextual information."""
    logger = logging.getLogger(name)

    extra: dict[str, Any] = {}
    if request:
        extra["endpoint"] = request.url.path
        extra["method"] = request.method
        # Try to get request_id from headers if present
        extra["request_id"] = request.headers.get("X-Request-ID", "N/A")

    return logging.LoggerAdapter(logger, extra)
