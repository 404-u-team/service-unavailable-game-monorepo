from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
import asyncpg

from src.api.routers.dependencies import get_connection_pool
from src.api.schemas import LoginRequest, RegisterRequest, UserResponse
from src.repositories.users import UserRepository
from src.services.auth import AuthService


router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(pool: asyncpg.Pool = Depends(get_connection_pool)) -> AuthService:
	return AuthService(UserRepository(pool))


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, service: AuthService = Depends(get_auth_service)):
    try:
        user, tokens = await service.register(data.login, str(data.email), data.password)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error 

    response = JSONResponse(status_code=status.HTTP_201_CREATED, content=UserResponse(
            id=user.id,
            login=user.login,
            email=user.email,
            balance=user.balance,
            created_at=user.created_at,
            updated_at=user.updated_at,
        ).model_dump(mode="json"),
    )
    response = _set_tokens_into_cookie(response, tokens)
    return response


@router.post("/login", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def login(data: LoginRequest, service: AuthService = Depends(get_auth_service)):
    try:
        user, tokens = await service.authenticate(data.login, data.password)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error 
	
    response = JSONResponse(status_code=status.HTTP_200_OK, content=UserResponse(
            id=user.id,
            login=user.login,
            email=user.email,
            balance=user.balance,
            created_at=user.created_at,
            updated_at=user.updated_at,
        ).model_dump(mode="json"),
    )
    response = _set_tokens_into_cookie(response, tokens)
    return response


@router.post("/refresh", status_code=status.HTTP_200_OK)
async def refresh(request: Request, service: AuthService = Depends(get_auth_service)):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не передан refresh_token"
        )
    try:
        tokens = service.refresh_tokens(refresh_token)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error

    response = _set_tokens_into_cookie(Response(), tokens)
    return response


def _set_tokens_into_cookie(response: Response, tokens: dict[str, str]) -> Response:
    """Вспомогательная функция для добавления токенов в куки ответа"""
    response.set_cookie(
        key="access_token",
        value=tokens["access_token"],
        max_age=900, # 15 минут
    )   
	
    response.set_cookie(
		key="refresh_token",
        value=tokens["refresh_token"],
        max_age=2592000, # 30 дней
    )   
	
    return response