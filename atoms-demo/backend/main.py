from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .generator import (
    build_prompt,
    build_repair_prompt,
    call_model,
    parse_generated_app,
    validate_generated_app,
)
from .models import (
    GenerateRequest,
    ProjectCreate,
    ProjectListItem,
    ProjectView,
    RestoreResponse,
)
from .repository import StudioRepository


DEMO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = DEMO_ROOT.parent
load_dotenv(REPOSITORY_ROOT / ".env")

database_path = Path(
    os.getenv("STUDIO_DB_PATH", str(DEMO_ROOT / "data" / "studio.db"))
)
static_path = Path(os.getenv("STUDIO_STATIC_DIR", str(DEMO_ROOT / "dist")))
repository = StudioRepository(database_path)

app = FastAPI(title="Quality Agent Studio API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)


def project_or_404(project_id: str, version: int | None = None) -> dict:
    try:
        return repository.get_project(project_id, version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="项目不存在") from exc


def sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "model_configured": bool(os.getenv("OPENAI_API_KEY")),
        "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
    }


@app.get("/api/studio/projects", response_model=list[ProjectListItem])
def list_projects() -> list[dict]:
    return repository.list_projects()


@app.post("/api/studio/projects", response_model=ProjectView, status_code=201)
def create_project(payload: ProjectCreate) -> dict:
    return repository.create_project(payload.title, payload.requirement)


@app.get("/api/studio/projects/{project_id}", response_model=ProjectView)
def get_project(project_id: str, version: int | None = None) -> dict:
    return project_or_404(project_id, version)


@app.post("/api/studio/projects/{project_id}/generate")
def generate_project(project_id: str, payload: GenerateRequest) -> StreamingResponse:
    project = project_or_404(project_id)
    if project["status"] == "generating":
        raise HTTPException(status_code=409, detail="该项目已有生成任务正在执行")

    def stream() -> Iterator[str]:
        repository.begin_generation(project_id, payload.instruction)
        completed = False
        yield sse("generation.stage", {"stage": "analysis", "message": "正在整理需求和当前版本"})
        current_html = project["version"]["html"] if project["version"] else None
        source_version = project["current_version"]
        prompt = build_prompt(project["requirement"], payload.instruction, current_html)

        try:
            raw_output = ""
            generated = None
            errors: list[str] = []
            for attempt in range(3):
                if attempt == 0:
                    yield sse("generation.stage", {"stage": "generation", "message": "正在调用模型生成完整应用"})
                else:
                    yield sse(
                        "generation.stage",
                        {
                            "stage": "repair",
                            "message": f"校验未通过，正在进行第 {attempt} 次自动修复",
                            "errors": errors,
                        },
                    )
                    prompt = build_repair_prompt(raw_output, errors)

                raw_output = call_model(prompt)
                yield sse("generation.stage", {"stage": "validation", "message": "正在校验文件结构和预览安全边界"})
                try:
                    generated = parse_generated_app(raw_output)
                    errors = validate_generated_app(generated)
                except ValueError as exc:
                    generated = None
                    errors = [str(exc)]
                if generated is not None and not errors:
                    break

            if generated is None or errors:
                raise RuntimeError("；".join(errors) or "生成内容未通过校验")

            saved = repository.save_version(
                project_id,
                generated.summary,
                generated.html,
                source_version=source_version,
            )
            completed = True
            yield sse(
                "generation.completed",
                {
                    "message": f"v{saved['current_version']} 已生成并保存",
                    "project": saved,
                },
            )
        except Exception as exc:
            failed = repository.mark_failed(project_id, str(exc))
            yield sse(
                "generation.failed",
                {"message": failed["error"] or "生成失败，请重试"},
            )
        finally:
            if not completed:
                latest = repository.get_project(project_id)
                if latest["status"] == "generating":
                    repository.mark_failed(project_id, "生成连接已中断，请重试")

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post(
    "/api/studio/projects/{project_id}/versions/{version}/restore",
    response_model=RestoreResponse,
)
def restore_version(project_id: str, version: int) -> dict:
    project_or_404(project_id, version)
    return {"project": repository.restore_version(project_id, version)}


if static_path.exists():
    assets_path = static_path / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str) -> FileResponse:
        requested = (static_path / full_path).resolve()
        if full_path and static_path.resolve() in requested.parents and requested.is_file():
            return FileResponse(requested)
        return FileResponse(static_path / "index.html")
