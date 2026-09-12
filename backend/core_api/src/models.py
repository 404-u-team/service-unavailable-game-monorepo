"""
Модели таблиц бд
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class User:
    id: UUID
    login: str
    email: str
    password_hash: str