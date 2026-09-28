import asyncio
import json
from collections.abc import AsyncIterator
from time import monotonic

from fastapi import Request

from app.v3.persistence.task_repository import TaskRepository
from app.v3.schemas.event import TaskEvent
from app.v3.schemas.task import TaskStatus


TERMINAL_STATUSES = {
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
}


def format_sse_event(
    event: TaskEvent,
) -> str:
    data = json.dumps(
        event.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return (
        f"id: {event.event_id}\n"
        f"event: {event.event_type.value}\n"
        f"data: {data}\n\n"
    )


async def stream_task_events(
    request: Request,
    repository: TaskRepository,
    task_id: str,
    after_id: int = 0,
    poll_interval: float = 0.25,
    heartbeat_interval: float = 15.0,
) -> AsyncIterator[str]:
    cursor = max(0, after_id)
    last_activity = monotonic()

    while True:
        if await request.is_disconnected():
            break

        events = await asyncio.to_thread(
            repository.list_events,
            task_id,
            cursor,
            100,
        )

        for event in events:
            cursor = event.event_id
            last_activity = monotonic()
            yield format_sse_event(event)

        task = await asyncio.to_thread(
            repository.get_task,
            task_id,
        )

        if task is None:
            break

        if task.status in TERMINAL_STATUSES:
            # 防止事件查询和终态更新之间发生竞态，
            # 在关闭连接前再读取一次剩余事件。
            remaining_events = await asyncio.to_thread(
                repository.list_events,
                task_id,
                cursor,
                100,
            )

            for event in remaining_events:
                cursor = event.event_id
                yield format_sse_event(event)

            break

        if (
            monotonic() - last_activity
            >= heartbeat_interval
        ):
            yield ": heartbeat\n\n"
            last_activity = monotonic()

        await asyncio.sleep(poll_interval)