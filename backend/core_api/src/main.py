from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI

from src.api.routers.auth import router as auth_router
from src.api.routers.health import router as health_router
from src.api.routers import dependencies
from src.config import settings

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
