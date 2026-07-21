import functools
import inspect
import logging
from typing import Any, Callable

from fastapi import HTTPException

logger = logging.getLogger("api_error_logger")

def api_error_handler(func: Callable) -> Callable:
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs) if inspect.iscoroutinefunction(func) else func(*args, **kwargs)
        except HTTPException:
            raise
        except Exception as e:
            endpoint_name = func.__name__
            logger.error(f"Error in endpoint '{endpoint_name}': {type(e).__name__}: {e}")
            raise

    return wrapper

