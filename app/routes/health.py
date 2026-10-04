from fastapi import APIRouter
from app.config import settings

router = APIRouter(tags=["Health & Status"])

@router.get("/health")
def health_check():
    """
    Check if the API service is active and report status.
    """
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "timezone": settings.DEFAULT_TIMEZONE,
    }
