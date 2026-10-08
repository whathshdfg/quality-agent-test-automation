from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StudioRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS studio_projects (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    requirement TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error TEXT,
                    current_version INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS studio_messages (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES studio_projects(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS studio_versions (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    summary TEXT NOT NULL,
                    html TEXT NOT NULL,
                    source_version INTEGER,
                    created_at TEXT NOT NULL,
                    UNIQUE(project_id, version),
                    FOREIGN KEY(project_id) REFERENCES studio_projects(id) ON DELETE CASCADE
                );
                """
            )
            connection.execute(
                """
                UPDATE studio_projects
                SET status = 'failed', error = '上一次生成因服务重启而中断', updated_at = ?
                WHERE status = 'generating'
                """,
                (utc_now(),),
            )

    def create_project(self, title: str, requirement: str) -> dict:
        project_id = f"prj_{uuid4().hex}"
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO studio_projects
                    (id, title, requirement, status, created_at, updated_at)
                VALUES (?, ?, ?, 'draft', ?, ?)
                """,
                (project_id, title.strip(), requirement.strip(), now, now),
            )
            self._add_message(connection, project_id, "user", requirement.strip())
        return self.get_project(project_id)

    def list_projects(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, title, status, current_version, created_at, updated_at
                FROM studio_projects
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_project(self, project_id: str, version: int | None = None) -> dict:
        with self.connect() as connection:
            project_row = connection.execute(
                "SELECT * FROM studio_projects WHERE id = ?", (project_id,)
            ).fetchone()
            if project_row is None:
                raise KeyError(project_id)

            selected_version = version if version is not None else project_row["current_version"]
            version_row = None
            if selected_version is not None:
                version_row = connection.execute(
                    """
                    SELECT version, summary, html, created_at
                    FROM studio_versions
                    WHERE project_id = ? AND version = ?
                    """,
                    (project_id, selected_version),
                ).fetchone()

            version_rows = connection.execute(
                """
                SELECT version, summary, created_at
                FROM studio_versions
                WHERE project_id = ?
                ORDER BY version DESC
                """,
                (project_id,),
            ).fetchall()
            message_rows = connection.execute(
                """
                SELECT id, role, content, created_at
                FROM studio_messages
                WHERE project_id = ?
                ORDER BY created_at, rowid
                """,
                (project_id,),
            ).fetchall()

        project = dict(project_row)
        project["version"] = dict(version_row) if version_row else None
        project["versions"] = [dict(row) for row in version_rows]
        project["messages"] = [dict(row) for row in message_rows]
        return project

    def begin_generation(self, project_id: str, instruction: str) -> dict:
        now = utc_now()
        with self.connect() as connection:
            exists = connection.execute(
                "SELECT id FROM studio_projects WHERE id = ?", (project_id,)
            ).fetchone()
            if exists is None:
                raise KeyError(project_id)
            connection.execute(
                """
                UPDATE studio_projects
                SET status = 'generating', error = NULL, updated_at = ?
                WHERE id = ?
                """,
                (now, project_id),
            )
            if instruction.strip():
                self._add_message(connection, project_id, "user", instruction.strip())
        return self.get_project(project_id)

    def save_version(
        self,
        project_id: str,
        summary: str,
        html: str,
        source_version: int | None = None,
    ) -> dict:
        now = utc_now()
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) AS latest FROM studio_versions WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            next_version = int(row["latest"]) + 1
            connection.execute(
                """
                INSERT INTO studio_versions
                    (id, project_id, version, summary, html, source_version, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"ver_{uuid4().hex}",
                    project_id,
                    next_version,
                    summary.strip(),
                    html,
                    source_version,
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE studio_projects
                SET status = 'ready', error = NULL, current_version = ?, updated_at = ?
                WHERE id = ?
                """,
                (next_version, now, project_id),
            )
            self._add_message(connection, project_id, "assistant", summary.strip())
        return self.get_project(project_id)

    def mark_failed(self, project_id: str, error: str) -> dict:
        now = utc_now()
        message = error.strip()[:2000]
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE studio_projects
                SET status = 'failed', error = ?, updated_at = ?
                WHERE id = ?
                """,
                (message, now, project_id),
            )
        return self.get_project(project_id)

    def restore_version(self, project_id: str, version: int) -> dict:
        project = self.get_project(project_id, version)
        selected = project["version"]
        if selected is None:
            raise KeyError(f"{project_id}:{version}")
        return self.save_version(
            project_id,
            f"已从 v{version} 恢复为新版本。{selected['summary']}",
            selected["html"],
            source_version=version,
        )

    @staticmethod
    def _add_message(
        connection: sqlite3.Connection,
        project_id: str,
        role: str,
        content: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO studio_messages (id, project_id, role, content, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (f"msg_{uuid4().hex}", project_id, role, content, utc_now()),
        )
