import asyncio
from functools import wraps

import structlog

from src.logging.exception_utils import into_dict


async def log_exception(func):
    """
    декоратор, что автоматически журналирует все поднимаемые ошибки в функции
    """
    log = structlog.get_logger(__name__)

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            await log.aexception("exception", **into_dict(e))
            raise e


async def log_silently(func):
    """
    декоратор, что журналирует все поднятые ошибки, но не поднимает их дальше
    """
    log = structlog.get_logger(__name__)

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            await log.aexception("exception", **into_dict(e))
