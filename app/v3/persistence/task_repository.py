import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from app.v3.core.config import settings
from app.v3.schemas.event import (
    TaskEvent,
    TaskEventType,
)
from app.v3.schemas.task import (
    TaskSnapshot,
    TaskStatus,
)


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
        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

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
                        CHECK (
                            model_mode IN ('api', 'rule')
                        ),

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
                        CHECK (
                            progress BETWEEN 0 AND 100
                        ),

                    result_json TEXT,
                    error_message TEXT,

                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS v3_task_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    node_name TEXT,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,

                    FOREIGN KEY (task_id)
                        REFERENCES v3_tasks(task_id)
                        ON DELETE CASCADE
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_v3_task_events_task_id_event_id
                ON v3_task_events (
                    task_id,
                    event_id
                )
                """
            )

    def _insert_event(
        self,
        connection: sqlite3.Connection,
        task_id: str,
        event_type: TaskEventType,
        node_name: str | None,
        payload: dict[str, Any],
        created_at: str,
    ) -> int:
        cursor = connection.execute(
            """
            INSERT INTO v3_task_events (
                task_id,
                event_type,
                node_name,
                payload_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                task_id,
                event_type.value,
                node_name,
                json.dumps(
                    payload,
                    ensure_ascii=False,
                ),
                created_at,
            ),
        )

        return int(cursor.lastrowid)

    @staticmethod
    def _row_to_event(
        row: sqlite3.Row,
    ) -> TaskEvent:
        return TaskEvent(
            event_id=row["event_id"],
            task_id=row["task_id"],
            event_type=TaskEventType(
                row["event_type"]
            ),
            node_name=row["node_name"],
            payload=json.loads(
                row["payload_json"]
            ),
            created_at=row["created_at"],
        )

    def create_task(
        self,
        requirement: str,
        model_mode: str = "api",
        task_id: str | None = None,
    ) -> TaskSnapshot:
        new_task_id = (
            task_id
            or f"task_{uuid4().hex}"
        )
        now = datetime.now(
            timezone.utc
        ).isoformat()

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

            self._insert_event(
                connection=connection,
                task_id=new_task_id,
                event_type=(
                    TaskEventType.TASK_QUEUED
                ),
                node_name=None,
                payload={
                    "model_mode": model_mode,
                    "progress": 0,
                },
                created_at=now,
            )

        return self._require_task(new_task_id)

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

    def _require_task(
        self,
        task_id: str,
    ) -> TaskSnapshot:
        task = self.get_task(task_id)

        if task is None:
            raise KeyError(
                f"任务不存在：{task_id}"
            )

        return task

    def list_events(
        self,
        task_id: str,
        after_id: int = 0,
        limit: int = 100,
    ) -> list[TaskEvent]:
        safe_after_id = max(
            0,
            int(after_id),
        )
        safe_limit = max(
            1,
            min(int(limit), 500),
        )

        with self._transaction() as connection:
            rows = connection.execute(
                """
                SELECT
                    event_id,
                    task_id,
                    event_type,
                    node_name,
                    payload_json,
                    created_at
                FROM v3_task_events
                WHERE task_id = ?
                  AND event_id > ?
                ORDER BY event_id ASC
                LIMIT ?
                """,
                (
                    task_id,
                    safe_after_id,
                    safe_limit,
                ),
            ).fetchall()

        return [
            self._row_to_event(row)
            for row in rows
        ]

    def append_event(
        self,
        task_id: str,
        event_type: TaskEventType,
        node_name: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> TaskEvent:
        self._require_task(task_id)

        now = datetime.now(
            timezone.utc
        ).isoformat()

        with self._transaction() as connection:
            event_id = self._insert_event(
                connection=connection,
                task_id=task_id,
                event_type=event_type,
                node_name=node_name,
                payload=payload or {},
                created_at=now,
            )

            row = connection.execute(
                """
                SELECT
                    event_id,
                    task_id,
                    event_type,
                    node_name,
                    payload_json,
                    created_at
                FROM v3_task_events
                WHERE event_id = ?
                """,
                (event_id,),
            ).fetchone()

        if row is None:
            raise RuntimeError(
                f"事件创建后无法读取：{event_id}"
            )

        return self._row_to_event(row)

    def mark_running(
        self,
        task_id: str,
    ) -> TaskSnapshot:
        now = datetime.now(
            timezone.utc
        ).isoformat()

        with self._transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE v3_tasks
                SET
                    status = ?,
                    current_node = ?,
                    progress = ?,
                    error_message = NULL,
                    updated_at = ?
                WHERE task_id = ?
                  AND status = ?
                """,
                (
                    TaskStatus.RUNNING.value,
                    "v2_workflow",
                    10,
                    now,
                    task_id,
                    TaskStatus.QUEUED.value,
                ),
            )

            updated = cursor.rowcount

            if updated:
                self._insert_event(
                    connection=connection,
                    task_id=task_id,
                    event_type=(
                        TaskEventType.TASK_STARTED
                    ),
                    node_name="v2_workflow",
                    payload={"progress": 10},
                    created_at=now,
                )

        if updated == 0:
            raise RuntimeError(
                "任务无法从 queued 进入 running："
                f"{task_id}"
            )

        return self._require_task(task_id)

    def complete_task(
        self,
        task_id: str,
        result: dict[str, Any],
    ) -> TaskSnapshot:
        now = datetime.now(
            timezone.utc
        ).isoformat()

        result_json = json.dumps(
            result,
            ensure_ascii=False,
        )

        with self._transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE v3_tasks
                SET
                    status = ?,
                    current_node = ?,
                    progress = ?,
                    result_json = ?,
                    error_message = NULL,
                    updated_at = ?
                WHERE task_id = ?
                  AND status = ?
                """,
                (
                    TaskStatus.COMPLETED.value,
                    "completed",
                    100,
                    result_json,
                    now,
                    task_id,
                    TaskStatus.RUNNING.value,
                ),
            )

            updated = cursor.rowcount

            if updated:
                self._insert_event(
                    connection=connection,
                    task_id=task_id,
                    event_type=(
                        TaskEventType.TASK_COMPLETED
                    ),
                    node_name="completed",
                    payload={"progress": 100},
                    created_at=now,
                )

        if updated == 0:
            raise RuntimeError(
                "任务无法从 running 进入 completed："
                f"{task_id}"
            )

        return self._require_task(task_id)

    def fail_task(
        self,
        task_id: str,
        error_message: str,
    ) -> TaskSnapshot:
        now = datetime.now(
            timezone.utc
        ).isoformat()

        with self._transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE v3_tasks
                SET
                    status = ?,
                    current_node = ?,
                    result_json = NULL,
                    error_message = ?,
                    updated_at = ?
                WHERE task_id = ?
                  AND status IN (?, ?)
                """,
                (
                    TaskStatus.FAILED.value,
                    "failed",
                    error_message,
                    now,
                    task_id,
                    TaskStatus.QUEUED.value,
                    TaskStatus.RUNNING.value,
                ),
            )

            updated = cursor.rowcount

            if updated:
                self._insert_event(
                    connection=connection,
                    task_id=task_id,
                    event_type=(
                        TaskEventType.TASK_FAILED
                    ),
                    node_name="failed",
                    payload={
                        "error_message": error_message
                    },
                    created_at=now,
                )

        if updated == 0:
            raise RuntimeError(
                f"任务无法进入 failed：{task_id}"
            )

        return self._require_task(task_id)