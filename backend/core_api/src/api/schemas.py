from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
	login: str = Field(min_length=3, max_length=255)
	email: EmailStr
	password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
	login: str
	password: str


class TokenResponse(BaseModel):
	access_token: str
	refresh_token: str


class UserResponse(BaseModel):
	id: UUID
	login: str
	email: EmailStr
	balance: int
	created_at: datetime
	updated_at: datetime
