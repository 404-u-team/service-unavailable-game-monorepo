"""
Модели таблиц бд
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class User:
    id: UUID
    login: str
    email: str
    password_hash: str
    balance: int
    created_at: datetime
    updated_at: datetime