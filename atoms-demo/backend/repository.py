from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Connection, Engine


metadata = MetaData()

projects = Table(
    "studio_projects",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("title", String(80), nullable=False),
    Column("requirement", Text, nullable=False),
    Column("status", String(20), nullable=False),
    Column("error", Text),
    Column("current_version", Integer),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
)

messages = Table(
    "studio_messages",
    metadata,
    Column("id", String(64), primary_key=True),
    Column(
        "project_id",
        String(64),
        ForeignKey("studio_projects.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("role", String(20), nullable=False),
    Column("content", Text, nullable=False),
    Column("created_at", String(40), nullable=False),
)

versions = Table(
    "studio_versions",
    metadata,
    Column("id", String(64), primary_key=True),
    Column(
        "project_id",
        String(64),
        ForeignKey("studio_projects.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("version", Integer, nullable=False),
    Column("summary", Text, nullable=False),
    Column("html", Text, nullable=False),
    Column("source_version", Integer),
    Column("created_at", String(40), nullable=False),
    UniqueConstraint("project_id", "version", name="uq_studio_project_version"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_database_url(database: str | Path) -> str:
    value = str(database).strip()
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    if "://" in value:
        return value

    path = Path(value).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.as_posix()}"


def build_engine(database: str | Path) -> Engine:
    database_url = normalize_database_url(database)
    connect_args = {"check_same_thread": False, "timeout": 30} if database_url.startswith("sqlite") else {}
    engine = create_engine(
        database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
    )
    if database_url.startswith("sqlite"):
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


class StudioRepository:
    def __init__(self, database: str | Path) -> None:
        self.database_url = normalize_database_url(database)
        self.engine = build_engine(self.database_url)
        self.backend_name = self.engine.dialect.name
        self._initialize()

    def _initialize(self) -> None:
        metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            connection.execute(
                update(projects)
                .where(projects.c.status == "generating")
                .values(
                    status="failed",
                    error="上一次生成因服务重启而中断",
                    updated_at=utc_now(),
                )
            )

    def create_project(self, title: str, requirement: str) -> dict:
        project_id = f"prj_{uuid4().hex}"
        now = utc_now()
        with self.engine.begin() as connection:
            connection.execute(
                insert(projects).values(
                    id=project_id,
                    title=title.strip(),
                    requirement=requirement.strip(),
                    status="draft",
                    created_at=now,
                    updated_at=now,
                )
            )
            self._add_message(connection, project_id, "user", requirement.strip())
        return self.get_project(project_id)

    def list_projects(self) -> list[dict]:
        statement = (
            select(
                projects.c.id,
                projects.c.title,
                projects.c.status,
                projects.c.current_version,
                projects.c.created_at,
                projects.c.updated_at,
            )
            .order_by(projects.c.updated_at.desc())
        )
        with self.engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [dict(row) for row in rows]

    def get_project(self, project_id: str, version: int | None = None) -> dict:
        with self.engine.connect() as connection:
            project_row = connection.execute(
                select(projects).where(projects.c.id == project_id)
            ).mappings().first()
            if project_row is None:
                raise KeyError(project_id)

            selected_version = version if version is not None else project_row["current_version"]
            version_row = None
            if selected_version is not None:
                version_row = connection.execute(
                    select(
                        versions.c.version,
                        versions.c.summary,
                        versions.c.html,
                        versions.c.created_at,
                    ).where(
                        versions.c.project_id == project_id,
                        versions.c.version == selected_version,
                    )
                ).mappings().first()

            version_rows = connection.execute(
                select(
                    versions.c.version,
                    versions.c.summary,
                    versions.c.created_at,
                )
                .where(versions.c.project_id == project_id)
                .order_by(versions.c.version.desc())
            ).mappings().all()
            message_rows = connection.execute(
                select(
                    messages.c.id,
                    messages.c.role,
                    messages.c.content,
                    messages.c.created_at,
                )
                .where(messages.c.project_id == project_id)
                .order_by(messages.c.created_at, messages.c.id)
            ).mappings().all()

        project = dict(project_row)
        project["version"] = dict(version_row) if version_row else None
        project["versions"] = [dict(row) for row in version_rows]
        project["messages"] = [dict(row) for row in message_rows]
        return project

    def begin_generation(self, project_id: str, instruction: str) -> dict:
        now = utc_now()
        with self.engine.begin() as connection:
            exists = connection.execute(
                select(projects.c.id).where(projects.c.id == project_id)
            ).first()
            if exists is None:
                raise KeyError(project_id)
            connection.execute(
                update(projects)
                .where(projects.c.id == project_id)
                .values(status="generating", error=None, updated_at=now)
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
        with self.engine.begin() as connection:
            project_row = connection.execute(
                select(projects.c.id)
                .where(projects.c.id == project_id)
                .with_for_update()
            ).first()
            if project_row is None:
                raise KeyError(project_id)

            latest = connection.execute(
                select(func.coalesce(func.max(versions.c.version), 0)).where(
                    versions.c.project_id == project_id
                )
            ).scalar_one()
            next_version = int(latest) + 1
            connection.execute(
                insert(versions).values(
                    id=f"ver_{uuid4().hex}",
                    project_id=project_id,
                    version=next_version,
                    summary=summary.strip(),
                    html=html,
                    source_version=source_version,
                    created_at=now,
                )
            )
            connection.execute(
                update(projects)
                .where(projects.c.id == project_id)
                .values(
                    status="ready",
                    error=None,
                    current_version=next_version,
                    updated_at=now,
                )
            )
            self._add_message(connection, project_id, "assistant", summary.strip())
        return self.get_project(project_id)

    def mark_failed(self, project_id: str, error: str) -> dict:
        now = utc_now()
        message = error.strip()[:2000]
        with self.engine.begin() as connection:
            connection.execute(
                update(projects)
                .where(projects.c.id == project_id)
                .values(status="failed", error=message, updated_at=now)
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
        connection: Connection,
        project_id: str,
        role: str,
        content: str,
    ) -> None:
        connection.execute(
            insert(messages).values(
                id=f"msg_{uuid4().hex}",
                project_id=project_id,
                role=role,
                content=content,
                created_at=utc_now(),
            )
        )
