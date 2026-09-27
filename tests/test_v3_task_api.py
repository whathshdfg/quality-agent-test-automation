import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.v3.api.dependencies import get_task_repository
from app.v3.persistence.task_repository import TaskRepository
from app.v3.schemas.task import TaskStatus


@pytest.fixture
def repository(tmp_path):
    return TaskRepository(
        tmp_path / "quality_agent_v3_test.db"
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


def test_repository_persists_created_task(tmp_path):
    db_path = tmp_path / "persistent_tasks.db"

    first_repository = TaskRepository(db_path)
    created = first_repository.create_task(
        requirement="测试重复支付",
        model_mode="rule",
    )

    second_repository = TaskRepository(db_path)
    loaded = second_repository.get_task(
        created.task_id
    )

    assert loaded is not None
    assert loaded.task_id == created.task_id
    assert loaded.requirement == "测试重复支付"
    assert loaded.model_mode == "rule"
    assert loaded.status == TaskStatus.QUEUED
    assert loaded.progress == 0


def test_create_task_endpoint_returns_accepted(
    client,
    repository,
):
    response = client.post(
        "/api/v3/tasks",
        json={
            "requirement": "测试重复支付",
            "model_mode": "rule",
        },
    )

    assert response.status_code == 202

    data = response.json()
    task_id = data["task_id"]

    assert task_id.startswith("task_")
    assert data["status"] == "queued"
    assert data["status_url"] == (
        f"/api/v3/tasks/{task_id}"
    )
    assert data["events_url"] == (
        f"/api/v3/tasks/{task_id}/events"
    )

    stored_task = repository.get_task(task_id)

    assert stored_task is not None
    assert stored_task.requirement == "测试重复支付"
    assert stored_task.status == TaskStatus.QUEUED


def test_get_task_endpoint_returns_persisted_task(
    client,
    repository,
):
    created = repository.create_task(
        requirement="测试订单取消",
        model_mode="api",
    )

    response = client.get(
        f"/api/v3/tasks/{created.task_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["task_id"] == created.task_id
    assert data["requirement"] == "测试订单取消"
    assert data["model_mode"] == "api"
    assert data["status"] == "queued"
    assert data["current_node"] is None
    assert data["progress"] == 0
    assert data["result"] is None
    assert data["error_message"] is None


def test_get_task_endpoint_returns_404(
    client,
):
    response = client.get(
        "/api/v3/tasks/task_not_found"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "任务不存在：task_not_found"
    )