import logging

from rq import Retry

from graph.state import FinalAnswerResult
from queueing import (
    get_qdrant_queue,
    qdrant_failure_ttl_seconds,
    qdrant_enabled,
    qdrant_job_timeout_seconds,
    qdrant_result_ttl_seconds,
    qdrant_retry_intervals,
)

logger = logging.getLogger(__name__)


def enqueue_qdrant_result(
    *,
    task_id: str | None,
    query: str,
    final_answer: FinalAnswerResult,
) -> None:
    """Enqueue best-effort persistence of a completed analysis in Qdrant."""
    if not qdrant_enabled():
        return

    try:
        retry_intervals = qdrant_retry_intervals()
        get_qdrant_queue().enqueue_call(
            func="qdrant.store_qdrant_result_job",
            args=(query, final_answer.model_dump(), task_id),
            timeout=qdrant_job_timeout_seconds(),
            result_ttl=qdrant_result_ttl_seconds(),
            failure_ttl=qdrant_failure_ttl_seconds(),
            retry=Retry(
                max=len(retry_intervals),
                interval=retry_intervals,
            ),
        )
    except Exception:
        logger.warning(
            "Nao foi possivel enfileirar a persistencia no Qdrant.",
            exc_info=True,
        )
