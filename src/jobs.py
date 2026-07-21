from rq import Retry, get_current_job

from final_results import store_final_result_job
from graph.workflow import workflow
from qdrant import try_save_final_answer
from queueing import (
    final_results_failure_ttl_seconds,
    final_results_job_timeout_seconds,
    final_results_result_ttl_seconds,
    final_results_retry_intervals,
    get_final_results_queue,
)


def process_analyze_job(query: str) -> dict:
    final_answer = None

    for chunk in workflow.stream({"query": query}, stream_mode="updates"):
        for _step, data in chunk.items():
            answer = data.get("final_answer")
            if answer is not None:
                final_answer = answer

    if final_answer is not None:
        job = get_current_job()

        if job is not None:
            retry_intervals = final_results_retry_intervals()
            get_final_results_queue().enqueue_call(
                func=store_final_result_job,
                args=(job.id, query, final_answer.model_dump()),
                timeout=final_results_job_timeout_seconds(),
                result_ttl=final_results_result_ttl_seconds(),
                failure_ttl=final_results_failure_ttl_seconds(),
                retry=Retry(
                    max=len(retry_intervals),
                    interval=retry_intervals,
                ),
            )

        try_save_final_answer(
            query=query,
            final_answer=final_answer,
            point_id=job.id if job is not None else None,
        )

    return {
        "status": "done",
        "query": query,
        "final_answer": final_answer.model_dump() if final_answer is not None else None,
    }
