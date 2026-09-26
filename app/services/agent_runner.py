from uuid import uuid4

from app.agent_graph_v2 import ModelMode, run_agent_v2
from app.db.run_repository import RunRepository


def new_run_id() -> str:
    return f"run_{uuid4().hex}"


def execute_agent(
    requirement: str,
    model_mode: ModelMode = "api",
    repository: RunRepository | None = None,
    workflow=run_agent_v2,
) -> dict:
    repository = repository or RunRepository()
    run_id = new_run_id()
    repository.create_run(
        requirement=requirement,
        run_id=run_id,
    )

    try:
        final_state = workflow(
            requirement,
            model_mode=model_mode,
            persist_outputs=True,
            persist_history=False,
            run_id=run_id,
        )
    except Exception as exc:
        repository.fail_run(run_id, str(exc))
        raise

    repository.complete_run(
        run_id=run_id,
        metrics=final_state["metrics"],
        trace=final_state["trace"],
        report=final_state["report"],
        rag_docs=len(final_state.get("rag_context", [])),
    )
    return final_state
