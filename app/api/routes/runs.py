from fastapi import APIRouter, HTTPException, Query

from app.db.run_repository import RunRepository
from app.schemas.run import RunDetail, RunListResponse


router = APIRouter(
    prefix="/api/runs",
    tags=["Agent Run History"],
)

repository: RunRepository | None = None


def get_repository() -> RunRepository:
    global repository
    if repository is None:
        repository = RunRepository()
    return repository


@router.get("", response_model=RunListResponse)
def list_agent_runs(
    limit: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
):
    return {
        "runs": get_repository().list_runs(
            limit=limit,
            status=status,
        )
    }


@router.get("/{run_id}", response_model=RunDetail)
def get_agent_run(run_id: str):
    run = get_repository().get_run(run_id)

    if run is None:
        raise HTTPException(
            status_code=404,
            detail="Agent run record not found.",
        )

    return run


@router.delete("/{run_id}")
def delete_agent_run(run_id: str):
    deleted = get_repository().delete_run(run_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Agent run record not found.",
        )

    return {
        "deleted": True,
        "run_id": run_id,
    }
