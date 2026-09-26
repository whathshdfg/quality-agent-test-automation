import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.v3.schemas.task import TaskCreateRequest


client = TestClient(app)


def test_v3_health_endpoint():
    response = client.get("/api/v3/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "quality-agent-v3",
        "version": "3.0.0",
    }


def test_task_create_request_normalizes_requirement():
    request = TaskCreateRequest(
        requirement="  测试重复支付  ",
    )

    assert request.requirement == "测试重复支付"
    assert request.model_mode == "api"


def test_task_create_request_rejects_blank_requirement():
    with pytest.raises(ValidationError):
        TaskCreateRequest(requirement="   ")


def test_task_create_request_rejects_invalid_model_mode():
    with pytest.raises(ValidationError):
        TaskCreateRequest(
            requirement="测试重复支付",
            model_mode="local",
        )