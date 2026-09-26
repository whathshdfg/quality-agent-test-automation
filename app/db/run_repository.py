import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.core.config import DATABASE_PATH


DEFAULT_DB_PATH = DATABASE_PATH


class RunRepository:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
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
            connection.execute("""
                CREATE TABLE IF NOT EXISTS agent_runs (
                    run_id TEXT PRIMARY KEY,
                    requirement TEXT NOT NULL,
                    status TEXT NOT NULL
                        CHECK (status IN ('running', 'completed', 'failed')),

                    total_cases INTEGER NOT NULL DEFAULT 0,
                    passed_cases INTEGER NOT NULL DEFAULT 0,
                    failed_cases INTEGER NOT NULL DEFAULT 0,

                    pass_rate REAL NOT NULL DEFAULT 0,
                    coverage_rate REAL NOT NULL DEFAULT 0,

                    retry_count INTEGER NOT NULL DEFAULT 0,
                    rag_docs INTEGER NOT NULL DEFAULT 0,
                    bug_count INTEGER NOT NULL DEFAULT 0,

                    metrics_json TEXT NOT NULL DEFAULT '{}',
                    trace_json TEXT NOT NULL DEFAULT '[]',
                    report TEXT NOT NULL DEFAULT '',
                    error_message TEXT,

                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

    def create_run(
        self,
        requirement: str,
        run_id: str | None = None,
    ) -> str:
        new_run_id = run_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with self._transaction() as connection:
            connection.execute("""
                INSERT INTO agent_runs (
                    run_id,
                    requirement,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                new_run_id,
                requirement,
                "running",
                now,
                now,
            ))

        return new_run_id

    def complete_run(
        self,
        run_id: str,
        metrics: dict[str, Any],
        trace: list[dict[str, Any]],
        report: str,
        rag_docs: int = 0,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()

        total_cases = int(
            metrics.get("total_cases", metrics.get("test_case_count", 0))
        )
        passed_cases = int(
            metrics.get("passed_cases", metrics.get("passed", 0))
        )
        failed_cases = int(
            metrics.get("failed_cases", metrics.get("failed", 0))
        )

        with self._transaction() as connection:
            cursor = connection.execute("""
                UPDATE agent_runs
                SET
                    status = ?,
                    total_cases = ?,
                    passed_cases = ?,
                    failed_cases = ?,
                    pass_rate = ?,
                    coverage_rate = ?,
                    retry_count = ?,
                    rag_docs = ?,
                    bug_count = ?,
                    metrics_json = ?,
                    trace_json = ?,
                    report = ?,
                    error_message = NULL,
                    updated_at = ?
                WHERE run_id = ?
            """, (
                "completed",
                total_cases,
                passed_cases,
                failed_cases,
                float(metrics.get("pass_rate", 0)),
                float(metrics.get(
                    "coverage_rate",
                    metrics.get("requirement_coverage_rate", 0),
                )),
                int(metrics.get("retry_count", metrics.get("enhancement_count", 0))),
                int(metrics.get("rag_docs", rag_docs)),
                int(metrics.get("bug_count", 0)),
                json.dumps(metrics, ensure_ascii=False),
                json.dumps(trace, ensure_ascii=False),
                report,
                now,
                run_id,
            ))

            if cursor.rowcount == 0:
                raise KeyError(f"运行记录不存在：{run_id}")

    def fail_run(self, run_id: str, error_message: str) -> None:
        now = datetime.now(timezone.utc).isoformat()

        with self._transaction() as connection:
            cursor = connection.execute("""
                UPDATE agent_runs
                SET
                    status = ?,
                    error_message = ?,
                    updated_at = ?
                WHERE run_id = ?
            """, (
                "failed",
                error_message,
                now,
                run_id,
            ))

            if cursor.rowcount == 0:
                raise KeyError(f"运行记录不存在：{run_id}")

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._transaction() as connection:
            row = connection.execute("""
                SELECT *
                FROM agent_runs
                WHERE run_id = ?
            """, (run_id,)).fetchone()

        if row is None:
            return None

        result = dict(row)
        result["metrics"] = json.loads(result.pop("metrics_json"))
        result["trace"] = json.loads(result.pop("trace_json"))
        return result

    def list_runs(
        self,
        limit: int = 20,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 100))

        with self._transaction() as connection:
            if status is None:
                rows = connection.execute("""
                    SELECT
                        run_id,
                        requirement,
                        status,
                        total_cases,
                        passed_cases,
                        failed_cases,
                        pass_rate,
                        coverage_rate,
                        retry_count,
                        rag_docs,
                        bug_count,
                        created_at,
                        updated_at
                    FROM agent_runs
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (safe_limit,)).fetchall()
            else:
                rows = connection.execute("""
                    SELECT
                        run_id,
                        requirement,
                        status,
                        total_cases,
                        passed_cases,
                        failed_cases,
                        pass_rate,
                        coverage_rate,
                        retry_count,
                        rag_docs,
                        bug_count,
                        created_at,
                        updated_at
                    FROM agent_runs
                    WHERE status = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (status, safe_limit)).fetchall()

        return [dict(row) for row in rows]

    def latest_run(self) -> dict[str, Any] | None:
        runs = self.list_runs(limit=1)
        if not runs:
            return None
        return self.get_run(runs[0]["run_id"])

    def delete_run(self, run_id: str) -> bool:
        with self._transaction() as connection:
            cursor = connection.execute("""
                DELETE FROM agent_runs
                WHERE run_id = ?
            """, (run_id,))

        return cursor.rowcount > 0
