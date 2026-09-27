import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.v3.api.dependencies import get_task_repository
from app.v3.persistence.task_repository import TaskRepository


@pytest.fixture
def repository(tmp_path):
    return TaskRepository(
        tmp_path / "task_events.db"
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


def test_create_task_records_queued_event(
    repository,
):
    task = repository.create_task(
        requirement="测试重复支付",
        model_mode="rule",
    )

    events = repository.list_events(
        task.task_id
    )

    assert len(events) == 1
    assert events[0].event_type.value == (
        "task.queued"
    )
    assert events[0].task_id == task.task_id
    assert events[0].payload == {
        "model_mode": "rule",
        "progress": 0,
    }


def test_task_lifecycle_records_events(
    repository,
):
    task = repository.create_task(
        requirement="测试订单取消",
        model_mode="rule",
    )

    repository.mark_running(task.task_id)
    repository.complete_task(
        task.task_id,
        result={"report": "# report"},
    )

    events = repository.list_events(
        task.task_id
    )

    assert [
        event.event_type.value
        for event in events
    ] == [
        "task.queued",
        "task.started",
        "task.completed",
    ]

    assert events[-1].payload == {
        "progress": 100
    }


def test_event_api_supports_after_id(
    client,
    repository,
):
    task = repository.create_task(
        requirement="测试支付",
        model_mode="rule",
    )
    repository.mark_running(task.task_id)
    repository.complete_task(
        task.task_id,
        result={},
    )

    all_response = client.get(
        f"/api/v3/tasks/{task.task_id}/events"
    )

    assert all_response.status_code == 200

    all_data = all_response.json()
    assert len(all_data["events"]) == 3

    first_event_id = (
        all_data["events"][0]["event_id"]
    )

    incremental_response = client.get(
        f"/api/v3/tasks/{task.task_id}/events",
        params={"after_id": first_event_id},
    )

    assert incremental_response.status_code == 200

    incremental_data = (
        incremental_response.json()
    )

    assert len(incremental_data["events"]) == 2
    assert all(
        event["event_id"] > first_event_id
        for event in incremental_data["events"]
    )


def test_event_api_returns_404(
    client,
):
    response = client.get(
        "/api/v3/tasks/task_missing/events"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "任务不存在：task_missing"
    )