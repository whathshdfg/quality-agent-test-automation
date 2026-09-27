from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from fastapi.encoders import jsonable_encoder

from app.agent_graph_v2 import run_agent_v2
from app.v3.core.config import settings
from app.v3.persistence.task_repository import TaskRepository
from app.v3.schemas.task import TaskSnapshot


Workflow = Callable[..., dict[str, Any]]


class TaskExecutor:
    def __init__(
        self,
        max_workers: int | None = None,
        workflow: Workflow = run_agent_v2,
    ):
        self._workflow = workflow
        self._pool = ThreadPoolExecutor(
            max_workers=(
                max_workers
                or settings.max_concurrent_jobs
            ),
            thread_name_prefix="quality-agent-v3",
        )

    def submit(
        self,
        task_id: str,
        repository: TaskRepository,
    ) -> Future[TaskSnapshot]:
        return self._pool.submit(
            self._run_task,
            task_id,
            repository,
        )

    def _run_task(
        self,
        task_id: str,
        repository: TaskRepository,
    ) -> TaskSnapshot:
        try:
            task = repository.mark_running(task_id)

            final_state = self._workflow(
                task.requirement,
                model_mode=task.model_mode,
                persist_outputs=False,
                persist_history=False,
                run_id=task.task_id,
            )

            result = jsonable_encoder(
                {
                    "run_id": final_state.get(
                        "run_id",
                        task.task_id,
                    ),
                    "report": final_state.get(
                        "report",
                        "",
                    ),
                    "metrics": final_state.get(
                        "metrics",
                        {},
                    ),
                    "bug_analysis": final_state.get(
                        "bug_analysis",
                        [],
                    ),
                    "unsupported_test_points": (
                        final_state.get(
                            "unsupported_test_points",
                            [],
                        )
                    ),
                }
            )

            return repository.complete_task(
                task_id=task_id,
                result=result,
            )

        except Exception as exc:
            error_message = (
                f"{type(exc).__name__}: {exc}"
            )[:2000]

            return repository.fail_task(
                task_id=task_id,
                error_message=error_message,
            )

    def shutdown(
        self,
        wait: bool = True,
    ) -> None:
        self._pool.shutdown(
            wait=wait,
            cancel_futures=False,
        )