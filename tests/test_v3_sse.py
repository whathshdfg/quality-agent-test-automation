import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.v3.api.dependencies import get_task_repository
from app.v3.persistence.task_repository import TaskRepository


@pytest.fixture
def repository(tmp_path):
    return TaskRepository(
        tmp_path / "task_sse.db"
    )


@pytest.fixture
def client(repository):
    app.dependency_overrides[
        get_task_repository
    ] = lambda: repository

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(
        get_task_repository,
        None,
    )


def create_completed_task(repository):
    task = repository.create_task(
        requirement="测试重复支付",
        model_mode="rule",
    )
    repository.mark_running(task.task_id)
    repository.complete_task(
        task.task_id,
        result={"report": "# report"},
    )
    return task


def test_sse_stream_returns_lifecycle_events(
    client,
    repository,
):
    task = create_completed_task(repository)

    response = client.get(
        f"/api/v3/tasks/{task.task_id}/events/stream"
    )

    assert response.status_code == 200
    assert response.headers[
        "content-type"
    ].startswith("text/event-stream")

    body = response.text

    assert "event: task.queued" in body
    assert "event: task.started" in body
    assert "event: task.completed" in body

    assert body.index(
        "event: task.queued"
    ) < body.index(
        "event: task.started"
    ) < body.index(
        "event: task.completed"
    )


def test_sse_stream_supports_last_event_id(
    client,
    repository,
):
    task = create_completed_task(repository)

    events = repository.list_events(
        task.task_id
    )
    first_event_id = events[0].event_id

    response = client.get(
        f"/api/v3/tasks/{task.task_id}/events/stream",
        headers={
            "Last-Event-ID": str(first_event_id)
        },
    )

    assert response.status_code == 200

    body = response.text

    assert "event: task.queued" not in body
    assert "event: task.started" in body
    assert "event: task.completed" in body


def test_sse_stream_rejects_invalid_last_event_id(
    client,
    repository,
):
    task = create_completed_task(repository)

    response = client.get(
        f"/api/v3/tasks/{task.task_id}/events/stream",
        headers={"Last-Event-ID": "invalid"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Last-Event-ID 必须是整数"
    )


def test_sse_stream_returns_404(
    client,
):
    response = client.get(
        "/api/v3/tasks/task_missing/events/stream"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "任务不存在：task_missing"
    )