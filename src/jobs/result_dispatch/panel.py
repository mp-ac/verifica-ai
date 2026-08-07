from rq import Retry

from final_results import store_final_result_job
from queueing import (
    final_results_failure_ttl_seconds,
    final_results_job_timeout_seconds,
    final_results_result_ttl_seconds,
    final_results_retry_intervals,
    get_final_results_queue,
)


def enqueue_panel_result(
    *,
    task_id: str,
    completed_result: dict,
) -> None:
    """Enqueue delivery of a completed analysis to the panel API."""
    retry_intervals = final_results_retry_intervals()
    get_final_results_queue().enqueue_call(
        func=store_final_result_job,
        args=(task_id, completed_result),
        timeout=final_results_job_timeout_seconds(),
        result_ttl=final_results_result_ttl_seconds(),
        failure_ttl=final_results_failure_ttl_seconds(),
        retry=Retry(
            max=len(retry_intervals),
            interval=retry_intervals,
        ),
    )
