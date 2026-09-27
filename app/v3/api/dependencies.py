from functools import lru_cache

from app.v3.persistence.task_repository import TaskRepository
from app.v3.services.task_executor import TaskExecutor


@lru_cache
def get_task_repository() -> TaskRepository:
    return TaskRepository()


@lru_cache
def get_task_executor() -> TaskExecutor:
    return TaskExecutor()