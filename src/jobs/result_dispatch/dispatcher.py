from rq import get_current_job

from graph.state import FinalAnswerResult
from jobs.result_dispatch.panel import enqueue_panel_result
from jobs.result_dispatch.qdrant import enqueue_qdrant_result


def dispatch_completed_result(
    *,
    query: str,
    final_answer: FinalAnswerResult,
    completed_result: dict,
    persist_to_qdrant: bool = True,
) -> None:
    """Enqueue the completed analysis for its external destinations."""
    job = get_current_job()
    task_id = job.id if job is not None else None

    if task_id is not None:
        enqueue_panel_result(
            task_id=task_id,
            completed_result=completed_result,
        )

    if persist_to_qdrant:
        enqueue_qdrant_result(
            task_id=task_id,
            query=query,
            final_answer=final_answer,
        )
