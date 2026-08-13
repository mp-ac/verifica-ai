from typing import Any

from rq import Retry
from rq.job import Job

from queueing import (
    final_results_failure_ttl_seconds,
    final_results_job_timeout_seconds,
    final_results_result_ttl_seconds,
    final_results_retry_intervals,
    get_final_results_queue,
)
from reanalysis.verificaai_painel import store_reanalysis_result_job


def enqueue_reanalysis_result(
    *,
    reanalysis_id: str,
    task_id: str,
    completed_result: dict[str, Any],
) -> None:
    """Enqueue a reanalysis result for delivery to VerificaAI Painel."""
    retry_intervals = final_results_retry_intervals()
    get_final_results_queue().enqueue_call(
        func=store_reanalysis_result_job,
        args=(reanalysis_id, task_id, completed_result),
        timeout=final_results_job_timeout_seconds(),
        result_ttl=final_results_result_ttl_seconds(),
        failure_ttl=final_results_failure_ttl_seconds(),
        retry=Retry(
            max=len(retry_intervals),
            interval=retry_intervals,
        ),
    )


def deliver_completed_reanalysis(
    job: Job,
    _connection: Any,
    result: Any,
) -> None:
    if not isinstance(result, dict):
        raise TypeError("A reanálise concluída devolveu um resultado inválido.")

    enqueue_reanalysis_result(
        reanalysis_id=_reanalysis_id(job),
        task_id=job.id,
        completed_result=result,
    )


def deliver_failed_reanalysis(
    job: Job,
    _connection: Any,
    _exception_type: type[BaseException],
    exception: BaseException,
    _traceback: Any,
) -> None:
    enqueue_reanalysis_result(
        reanalysis_id=_reanalysis_id(job),
        task_id=job.id,
        completed_result={
            "status": "failed",
            "result": None,
            "execution": None,
            "error": str(exception) or "A reanálise falhou.",
        },
    )


def deliver_stopped_reanalysis(job: Job, _connection: Any) -> None:
    enqueue_reanalysis_result(
        reanalysis_id=_reanalysis_id(job),
        task_id=job.id,
        completed_result={
            "status": "failed",
            "result": None,
            "execution": None,
            "error": "A execução da reanálise foi interrompida.",
        },
    )


def _reanalysis_id(job: Job) -> str:
    if not job.args or not isinstance(job.args[0], str):
        raise ValueError("O job não possui um reanalysis_id válido.")

    return job.args[0]
