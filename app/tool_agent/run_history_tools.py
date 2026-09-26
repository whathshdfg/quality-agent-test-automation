from app.db.run_repository import RunRepository


def get_run_history(limit: int = 10, status: str | None = None) -> dict:
    repository = RunRepository()
    return {
        "success": True,
        "runs": repository.list_runs(limit=limit, status=status),
    }


def get_run_detail(run_id: str) -> dict:
    repository = RunRepository()
    run = repository.get_run(run_id)
    if run is None:
        return {
            "success": False,
            "error": f"agent run not found: {run_id}",
        }
    return {
        "success": True,
        "run": run,
    }
