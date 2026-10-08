from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    requirement: str = Field(min_length=20, max_length=12_000)


class GenerateRequest(BaseModel):
    instruction: str = Field(default="", max_length=6_000)


class MessageView(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: str


class VersionSummary(BaseModel):
    version: int
    summary: str
    created_at: str


class VersionView(VersionSummary):
    html: str


class ProjectView(BaseModel):
    id: str
    title: str
    requirement: str
    status: Literal["draft", "generating", "ready", "failed"]
    error: str | None
    current_version: int | None
    version: VersionView | None
    versions: list[VersionSummary]
    messages: list[MessageView]
    created_at: str
    updated_at: str


class ProjectListItem(BaseModel):
    id: str
    title: str
    status: Literal["draft", "generating", "ready", "failed"]
    current_version: int | None
    created_at: str
    updated_at: str


class RestoreResponse(BaseModel):
    project: ProjectView
