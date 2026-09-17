import asyncpg

from src.models import User


class UserRepository:
    """Класс для доступа к Users таблице"""
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def create(self, login: str, email: str, password_hash: str) -> User:
        """
        Создание пользователя

        Args:
            login (str): login пользователя
            email (str): Почта пользователя
            password_hash (str): Хеш пароля пользователя
        
        Returns:
            User: Объект пользователя

        Raises:
            ValueError: Возможные значения
                "При конфлиекте логина и/или почты"
                "INSERT ... RETURNING вернуло None"
        """
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    row = await connection.fetchrow(
                        """
                        INSERT INTO users (login, email, password_hash)
                        VALUES ($1, $2, $3)
                        RETURNING id, login, email, password_hash, balance, created_at, updated_at
                        """,
                        login,
                        email,
                        password_hash,
                    )
        except asyncpg.UniqueViolationError:
            raise ValueError("Пользователь с таким логином или почтой уже существует")

        if row is None:
            raise ValueError("INSERT ... RETURNING вернуло None")
        return User(*row)

    async def find_by_login(self, login: str) -> User | None:
        """
        Получить пользователя по логину

        Args:
            login (str): Логин пользователя

        Returns:
            User | None: Объект пользователя, если найден, иначе None
        """
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(
                "SELECT id, login, email, password_hash, balance, created_at, updated_at "
                "FROM users WHERE login = $1",
                login,
            )
        return User(*row) if row else None