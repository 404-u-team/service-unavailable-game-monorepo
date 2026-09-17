from collections.abc import AsyncIterator

import asyncpg


pool: asyncpg.Pool | None = None


async def get_connection_pool() -> AsyncIterator[asyncpg.Pool]:
    if pool is None:
        raise RuntimeError("Пул подключений к БД не инициализирован")
    yield pool