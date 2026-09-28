from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import StreamingResponse
from app.v3.schemas.event import TaskEventListResponse
from app.v3.api.dependencies import (
    get_task_executor,
    get_task_repository,
)
from app.v3.services.event_stream import (
    stream_task_events,
)
from app.v3.services.task_executor import TaskExecutor
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
    executor: TaskExecutor = Depends(
        get_task_executor
    ),
) -> TaskAcceptedResponse:
    task = repository.create_task(
        requirement=request.requirement,
        model_mode=request.model_mode,
    )

    executor.submit(
        task_id=task.task_id,
        repository=repository,
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
        stream_url=(
            f"{settings.api_prefix}/tasks/"
            f"{task.task_id}/events/stream"
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
@router.get(
    "/tasks/{task_id}/events",
    response_model=TaskEventListResponse,
)
def get_task_events(
    task_id: str,
    after_id: int = Query(
        default=0,
        ge=0,
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
    repository: TaskRepository = Depends(
        get_task_repository
    ),
) -> TaskEventListResponse:
    task = repository.get_task(task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务不存在：{task_id}",
        )

    events = repository.list_events(
        task_id=task_id,
        after_id=after_id,
        limit=limit,
    )

    next_after_id = (
        events[-1].event_id
        if events
        else after_id
    )

    return TaskEventListResponse(
        events=events,
        next_after_id=next_after_id,
    )
@router.get(
    "/tasks/{task_id}/events/stream",
)
async def stream_task_events_endpoint(
    task_id: str,
    request: Request,
    after_id: int = Query(
        default=0,
        ge=0,
    ),
    last_event_id: str | None = Header(
        default=None,
        alias="Last-Event-ID",
    ),
    repository: TaskRepository = Depends(
        get_task_repository
    ),
):
    task = repository.get_task(task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务不存在：{task_id}",
        )

    cursor = after_id

    if last_event_id is not None:
        try:
            parsed_last_event_id = int(
                last_event_id
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="Last-Event-ID 必须是整数",
            ) from exc

        if parsed_last_event_id < 0:
            raise HTTPException(
                status_code=400,
                detail="Last-Event-ID 不能小于 0",
            )

        cursor = max(
            cursor,
            parsed_last_event_id,
        )

    event_generator = stream_task_events(
        request=request,
        repository=repository,
        task_id=task_id,
        after_id=cursor,
        poll_interval=(
            settings.sse_poll_interval_seconds
        ),
        heartbeat_interval=(
            settings.sse_heartbeat_seconds
        ),
    )

    return StreamingResponse(
        event_generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )