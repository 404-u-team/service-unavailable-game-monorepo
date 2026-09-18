from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from pwdlib import PasswordHash

from src.config import settings
from src.logging.wrappers import log_exception
from src.repositories.users import User, UserRepository


class AuthService:
    """
    Auth сервис
    Отвечает за регистрацию, авторизацию, создание jwt токенов, обновление токенов
    """

    password_hash = PasswordHash.recommended()

    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    async def register(
        self, login: str, email: str, password: str
    ) -> tuple[User, dict]:
        """
        Регистрация пользователя

        Args:
            login (str): Логин пользователя.
            email (str): Электронная почта пользователя.
            password (str): Пароль пользователя.

        Returns:
            tuple[User, dict]: Созданный пользователь и пара JWT-токенов.

        Raises:
            ValueError: Пользователь с таким логином или почтой уже существует.
        """
        created_user = await self.repository.create(
            login, email, self.password_hash.hash(password)
        )
        tokens = self.create_tokens(user_id=created_user.id)
        return created_user, tokens

    async def authenticate(self, login: str, password: str) -> tuple[User, dict]:
        """
        Авторизация пользователя

        Args:
            login (str): Логин пользователя.
            password (str): Пароль пользователя.

        Returns:
            tuple[User, dict]: Пользователь и пара JWT-токенов.

        Raises:
            ValueError: Логин не найден или пароль неверный.
        """
        user = await self.repository.find_by_login(login)
        if user is None or not self.password_hash.verify(password, user.password_hash):
            raise ValueError("Неккоректный логин или пароль")

        tokens = self.create_tokens(user_id=user.id)
        return user, tokens

    def create_tokens(self, user_id: UUID) -> dict[str, str]:
        """
        Создает пару JWT токенов (access, refresh)

        Args:
            user_id (UUID): Идентификатор пользователя, которому принадлежат токены.

        Returns:
            dict[str, str]: Словарь с access и refresh токенами.
        """
        return {
            "access_token": self._create_token(
                user_id,
                "access",
                timedelta(minutes=settings.access_token_expire_minutes),
            ),
            "refresh_token": self._create_token(
                user_id, "refresh", timedelta(days=settings.refresh_token_expire_days)
            ),
        }

    def refresh_tokens(self, token: str) -> dict[str, str]:
        """
        Обновление токенов

        Args:
            token (str): Refresh JWT-токен.

        Returns:
            dict[str, str]: Новая пара access и refresh токенов.

        Raises:
            ValueError: Неккоректный refresh_token
        """
        try:
            payload = jwt.decode(
                token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
            )
        except jwt.InvalidTokenError as error:
            raise ValueError("Неккоректный refresh_token") from error
        if payload.get("type") != "refresh" or not payload.get("sub"):
            raise ValueError("Неккоректный refresh_token")
        return self.create_tokens(UUID(payload["sub"]))

    @staticmethod
    def _create_token(user_id: UUID, token_type: str, lifetime: timedelta) -> str:
        """
        Создание JWT токена

        Args:
            user_id (UUID): Идентификатор пользователя.
            token_type (str): Тип токена, например access или refresh.
            lifetime (timedelta): Срок действия токена.

        Returns:
            str: Подписанный JWT-токен.
        """
        now = datetime.now(UTC)
        return jwt.encode(
            {
                "sub": str(user_id),
                "type": token_type,
                "iat": now,
                "exp": now + lifetime,
                "jti": str(uuid4()),
            },
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
