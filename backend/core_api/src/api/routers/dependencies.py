from collections.abc import AsyncIterator

import asyncpg

from src.config import settings


pool: asyncpg.Pool | None = None


async def get_connection() -> AsyncIterator[asyncpg.Pool]:
    if pool is None:
        raise RuntimeError("Database pool is not initialized")
    yield pool