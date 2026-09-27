from functools import lru_cache

from app.v3.persistence.task_repository import TaskRepository


@lru_cache
def get_task_repository() -> TaskRepository:
    return TaskRepository()