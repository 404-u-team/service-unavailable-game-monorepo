import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID

import asyncpg

from src.simulation.models import Game


class SaveNotFound(LookupError):
    pass


class GameRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def list(self, owner: str) -> list[asyncpg.Record]:
        return await self.pool.fetch(
            """
            SELECT id, state->>'name' AS name, state->>'scenario' AS scenario,
                   COALESCE((state->>'start_minute')::integer, 0) AS start_minute,
                   (state->>'tick')::integer AS tick, (state->>'audience')::float AS audience,
                   (state->>'balance')::float AS balance, saved_at
            FROM games WHERE owner = $1 ORDER BY saved_at DESC
            """,
            owner,
        )

    async def create(self, owner: str, game: Game) -> None:
        await self.pool.execute(
            """
            INSERT INTO games (owner, id, state, clock_at, saved_at)
            VALUES ($1, $2, $3::jsonb, clock_timestamp(), clock_timestamp())
            ON CONFLICT (owner, id) DO NOTHING
            """,
            owner,
            game.id,
            game.model_dump_json(),
        )

    @asynccontextmanager
    async def lock(
        self, owner: str, game_id: UUID
    ) -> AsyncIterator[tuple[asyncpg.Connection, asyncpg.Record]]:
        async with self.pool.acquire() as connection, connection.transaction():
            row = await connection.fetchrow(
                "SELECT state, clock_at, saved_at FROM games WHERE owner = $1 AND id = $2 FOR UPDATE",
                owner,
                game_id,
            )
            if row is None:
                raise SaveNotFound
            yield connection, row

    async def record_action(
        self,
        connection: asyncpg.Connection,
        owner: str,
        game_id: UUID,
        request_id: UUID,
        fingerprint: str,
    ) -> bool:
        row = await connection.fetchrow(
            """
            INSERT INTO game_actions (owner, game_id, request_id, fingerprint) VALUES ($1, $2, $3, $4)
            ON CONFLICT DO NOTHING RETURNING fingerprint
            """,
            owner,
            game_id,
            request_id,
            fingerprint,
        )
        if row is not None:
            return True
        existing = await connection.fetchval(
            "SELECT fingerprint FROM game_actions WHERE owner = $1 AND game_id = $2 AND request_id = $3",
            owner,
            game_id,
            request_id,
        )
        if existing != fingerprint:
            raise ValueError("This request ID was already used for a different action.")
        return False

    async def save(
        self,
        connection: asyncpg.Connection,
        owner: str,
        game: Game,
        clock_at: datetime,
        saved_at: datetime,
    ) -> None:
        await connection.execute(
            "UPDATE games SET state = $3::jsonb, clock_at = $4, saved_at = $5 WHERE owner = $1 AND id = $2",
            owner,
            game.id,
            game.model_dump_json(),
            clock_at,
            saved_at,
        )

    @staticmethod
    def restore(row: asyncpg.Record) -> Game:
        return Game.model_validate(json.loads(row["state"]))
