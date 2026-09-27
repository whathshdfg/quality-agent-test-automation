from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from app.v3.api.dependencies import get_task_repository
from app.v3.core.config import settings
from app.v3.persistence.task_repository import TaskRepository
from app.v3.schemas.health import HealthResponse
from app.v3.schemas.task import (
    TaskAcceptedResponse,
    TaskCreateRequest,
    TaskSnapshot,
)


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


@router.post(
    "/tasks",
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_task(
    request: TaskCreateRequest,
    repository: TaskRepository = Depends(
        get_task_repository
    ),
) -> TaskAcceptedResponse:
    task = repository.create_task(
        requirement=request.requirement,
        model_mode=request.model_mode,
    )

    return TaskAcceptedResponse(
        task_id=task.task_id,
        status=task.status,
        status_url=(
            f"{settings.api_prefix}/tasks/{task.task_id}"
        ),
        events_url=(
            f"{settings.api_prefix}/tasks/"
            f"{task.task_id}/events"
        ),
    )


@router.get(
    "/tasks/{task_id}",
    response_model=TaskSnapshot,
)
def get_task(
    task_id: str,
    repository: TaskRepository = Depends(
        get_task_repository
    ),
) -> TaskSnapshot:
    task = repository.get_task(task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务不存在：{task_id}",
        )

    return task