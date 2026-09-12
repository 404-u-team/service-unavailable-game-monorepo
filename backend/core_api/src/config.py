"""
Файл с конфигурацией
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	database_url: str = "postgresql://postgres:postgres@db:5432/core_api"
	jwt_secret: str = "change-me-in-production-use-a-strong-secret"
	jwt_algorithm: str = "HS256"
	access_token_expire_minutes: int = 30
	refresh_token_expire_days: int = 30

	model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


# Объект для глобального доступа
settings = Settings()
