from contextlib import asynccontextmanager
from logging import INFO, basicConfig
from sys import stdout

import asyncpg
import structlog
from fastapi import FastAPI

from src.api.routers import dependencies
from src.api.routers.auth import router as auth_router
from src.api.routers.health import router as health_router
from src.config import settings

# Настраиваем журналирование
basicConfig(
    format="%(message)s", stream=stdout, level=INFO
)  # можно будет заменить на конкретный файл через ENV, если нужно

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)


# ----------------------------------
# Lifespan для закрытия пула
# подключений при завершении работы
# ----------------------------------
@asynccontextmanager
async def lifespan(_: FastAPI):
    dependencies.pool = await asyncpg.create_pool(settings.database_url)
    yield
    await dependencies.pool.close()


# -----------------------------------------
# Создаем объект app и добавляем routers
# -----------------------------------------
app = FastAPI(title="Core API", lifespan=lifespan)

app.include_router(auth_router, prefix="/api")
app.include_router(health_router, prefix="/api")
