from fastapi import APIRouter, status


router = APIRouter(prefix="", tags=["health"])


@router.get("/health", status_code=status.HTTP_200_OK)
def health():
    return {"status": "healthy"}