from fastapi import FastAPI
import functools
import logging
import traceback
import inspect
from fastapi import HTTPException
from typing import Callable, Any

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

