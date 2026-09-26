from fastapi import APIRouter

from app.v3.core.config import settings
from app.v3.schemas.health import HealthResponse


router = APIRouter(
    prefix=settings.api_prefix,
    tags=["V3"],
)


@router.get(
    "/health",
    response_model=HealthResponse,
)
def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        version=settings.version,
    )