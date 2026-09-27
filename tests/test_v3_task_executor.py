from app.v3.persistence.task_repository import TaskRepository
from app.v3.schemas.task import TaskStatus
from app.v3.services.task_executor import TaskExecutor


def test_executor_completes_task(tmp_path):
    repository = TaskRepository(
        tmp_path / "executor_success.db"
    )
    task = repository.create_task(
        requirement="测试重复支付",
        model_mode="rule",
    )

    captured = {}

    def fake_workflow(
        requirement,
        **kwargs,
    ):
        captured["requirement"] = requirement
        captured.update(kwargs)

        return {
            "run_id": kwargs["run_id"],
            "report": "# 测试报告",
            "metrics": {
                "total_cases": 3,
                "passed_cases": 3,
                "failed_cases": 0,
            },
            "bug_analysis": [],
            "unsupported_test_points": [],
        }

    executor = TaskExecutor(
        max_workers=1,
        workflow=fake_workflow,
    )

    try:
        future = executor.submit(
            task.task_id,
            repository,
        )
        completed = future.result(timeout=5)
    finally:
        executor.shutdown()

    assert completed.status == TaskStatus.COMPLETED
    assert completed.current_node == "completed"
    assert completed.progress == 100
    assert completed.error_message is None

    assert completed.result is not None
    assert completed.result["report"] == "# 测试报告"
    assert completed.result["metrics"]["passed_cases"] == 3

    assert captured == {
        "requirement": "测试重复支付",
        "model_mode": "rule",
        "persist_outputs": False,
        "persist_history": False,
        "run_id": task.task_id,
    }

    stored = repository.get_task(task.task_id)

    assert stored is not None
    assert stored.status == TaskStatus.COMPLETED
    assert stored.result == completed.result


def test_executor_marks_task_failed(tmp_path):
    repository = TaskRepository(
        tmp_path / "executor_failure.db"
    )
    task = repository.create_task(
        requirement="测试订单取消",
        model_mode="rule",
    )

    def failing_workflow(
        requirement,
        **kwargs,
    ):
        raise RuntimeError("workflow exploded")

    executor = TaskExecutor(
        max_workers=1,
        workflow=failing_workflow,
    )

    try:
        future = executor.submit(
            task.task_id,
            repository,
        )
        failed = future.result(timeout=5)
    finally:
        executor.shutdown()

    assert failed.status == TaskStatus.FAILED
    assert failed.current_node == "failed"
    assert failed.result is None
    assert failed.error_message == (
        "RuntimeError: workflow exploded"
    )

    stored = repository.get_task(task.task_id)

    assert stored is not None
    assert stored.status == TaskStatus.FAILED
    assert stored.error_message == (
        "RuntimeError: workflow exploded"
    )