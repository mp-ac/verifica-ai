import logging
import os

from rq import Retry, get_current_job

from final_results import store_final_result_job
from graph.workflow import workflow
from queueing import (
    final_results_failure_ttl_seconds,
    final_results_job_timeout_seconds,
    final_results_result_ttl_seconds,
    final_results_retry_intervals,
    get_final_results_queue,
    get_qdrant_queue,
    qdrant_failure_ttl_seconds,
    qdrant_enabled,
    qdrant_job_timeout_seconds,
    qdrant_result_ttl_seconds,
    qdrant_retry_intervals,
)

logger = logging.getLogger(__name__)


def process_analyze_job(query: str) -> dict:
    final_answer = None
    executed_agents = set()
    executed_tools = set()

    for chunk in workflow.stream({"query": query}, stream_mode="updates"):
        for step, data in chunk.items():
            if step in {"search_agent", "transcription_agent"}:
                executed_agents.add(step)

            executed_tools.update(data.get("tools", []))

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

        if qdrant_enabled():
            try:
                retry_intervals = qdrant_retry_intervals()
                get_qdrant_queue().enqueue_call(
                    func="qdrant.store_qdrant_result_job",
                    args=(
                        query,
                        final_answer.model_dump(),
                        job.id if job is not None else None,
                    ),
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

    return {
        "status": "done",
        "query": query,
        "final_answer": final_answer.model_dump() if final_answer is not None else None,
        "execution": {
            "models": [
                {
                    "role": "router",
                    "provider": os.getenv("ROUTER_PROVIDER", "vllm"),
                    "model": os.getenv("ROUTER_MODEL", ""),
                },
                {
                    "role": "search",
                    "provider": os.getenv("SEARCH_PROVIDER", "vllm"),
                    "model": os.getenv("SEARCH_MODEL", ""),
                },
            ],
            "agents": sorted(executed_agents),
            "tools": sorted(executed_tools),
        },
    }
