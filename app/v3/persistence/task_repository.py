import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from app.v3.core.config import settings
from app.v3.schemas.task import TaskSnapshot, TaskStatus


class TaskRepository:
    def __init__(
        self,
        db_path: str | Path = settings.database_path,
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.init_db()

    @contextmanager
    def _transaction(
        self,
    ) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(
            self.db_path,
            timeout=30,
        )
        connection.row_factory = sqlite3.Row

        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def init_db(self) -> None:
        with self._transaction() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS v3_tasks (
                    task_id TEXT PRIMARY KEY,
                    requirement TEXT NOT NULL,
                    model_mode TEXT NOT NULL
                        CHECK (model_mode IN ('api', 'rule')),

                    status TEXT NOT NULL
                        CHECK (
                            status IN (
                                'queued',
                                'running',
                                'completed',
                                'failed',
                                'cancelling',
                                'cancelled'
                            )
                        ),

                    current_node TEXT,
                    progress INTEGER NOT NULL DEFAULT 0
                        CHECK (progress BETWEEN 0 AND 100),

                    result_json TEXT,
                    error_message TEXT,

                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def create_task(
        self,
        requirement: str,
        model_mode: str = "api",
        task_id: str | None = None,
    ) -> TaskSnapshot:
        new_task_id = task_id or f"task_{uuid4().hex}"
        now = datetime.now(timezone.utc).isoformat()

        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO v3_tasks (
                    task_id,
                    requirement,
                    model_mode,
                    status,
                    current_node,
                    progress,
                    result_json,
                    error_message,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_task_id,
                    requirement,
                    model_mode,
                    TaskStatus.QUEUED.value,
                    None,
                    0,
                    None,
                    None,
                    now,
                    now,
                ),
            )

        created_task = self.get_task(new_task_id)

        if created_task is None:
            raise RuntimeError(
                f"任务创建后无法读取：{new_task_id}"
            )

        return created_task

    def get_task(
        self,
        task_id: str,
    ) -> TaskSnapshot | None:
        with self._transaction() as connection:
            row = connection.execute(
                """
                SELECT
                    task_id,
                    requirement,
                    model_mode,
                    status,
                    current_node,
                    progress,
                    result_json,
                    error_message,
                    created_at,
                    updated_at
                FROM v3_tasks
                WHERE task_id = ?
                """,
                (task_id,),
            ).fetchone()

        if row is None:
            return None

        result = (
            json.loads(row["result_json"])
            if row["result_json"]
            else None
        )

        return TaskSnapshot(
            task_id=row["task_id"],
            requirement=row["requirement"],
            model_mode=row["model_mode"],
            status=TaskStatus(row["status"]),
            current_node=row["current_node"],
            progress=row["progress"],
            result=result,
            error_message=row["error_message"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )