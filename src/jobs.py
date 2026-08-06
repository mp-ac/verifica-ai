import logging
import os
from datetime import datetime, timezone
from time import perf_counter

from rq import Retry, get_current_job

from config import ATTACHMENTS_MAX_ITEMS
from final_results import store_final_result_job
from graph.workflow import workflow
from llm_settings import get_image_settings
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
from utils.attachments import normalize_attachments
from utils.token_usage import TOKEN_USAGE_FIELDS, empty_token_usage

logger = logging.getLogger(__name__)


def process_analyze_job(
    query: str | None,
    attachments: list[dict] | None = None,
) -> dict:
    started_at = perf_counter()
    normalized_attachments = normalize_attachments(
        query,
        attachments or [],
        max_items=ATTACHMENTS_MAX_ITEMS,
    )
    workflow_query = (query or "").strip() or "Conteúdo enviado para análise"
    final_answer = None
    executed_agents = set()
    executed_tools = set()
    usage_by_role = {
        role: empty_token_usage()
        for role in ("router", "search", "image")
    }

    for chunk in workflow.stream(
        {
            "query": workflow_query,
            "attachments": normalized_attachments,
        },
        stream_mode="updates",
    ):
        for step, data in chunk.items():
            if step in {"search_agent", "transcription_agent", "image_agent"}:
                executed_agents.add(step)

            executed_tools.update(data.get("tools", []))

            for model_usage in data.get("model_usage", []):
                role = model_usage["role"]
                for field in TOKEN_USAGE_FIELDS:
                    usage_by_role[role][field] += model_usage.get(field, 0)

            answer = data.get("final_answer")
            if answer is not None:
                final_answer = answer

    duration_ms = round((perf_counter() - started_at) * 1000)
    completed_at = datetime.now(timezone.utc).isoformat()
    final_answer_data = (
        final_answer.model_dump() if final_answer is not None else None
    )
    execution_models = [
        {
            "role": "router",
            "provider": os.getenv("ROUTER_PROVIDER", "vllm"),
            "model": os.getenv("ROUTER_MODEL", ""),
            "usage": usage_by_role["router"],
        },
        {
            "role": "search",
            "provider": os.getenv("SEARCH_PROVIDER", "vllm"),
            "model": os.getenv("SEARCH_MODEL", ""),
            "usage": usage_by_role["search"],
        },
    ]

    if "image_agent" in executed_agents:
        image_settings = get_image_settings()
        execution_models.append(
            {
                "role": "image",
                "provider": image_settings.provider,
                "model": image_settings.model,
                "usage": usage_by_role["image"],
            }
        )

    execution = {
        "models": execution_models,
        "agents": sorted(executed_agents),
        "tools": sorted(executed_tools),
        "duration_ms": duration_ms,
        "completed_at": completed_at,
        "app_version": os.getenv("APP_VERSION", "0.0.1"),
    }
    completed_result = {
        "status": "done",
        "result": {
            "query": workflow_query,
            "attachments": normalized_attachments,
            "final_answer": final_answer_data,
        },
        "execution": execution,
        "error": None,
    }

    if final_answer is not None:
        job = get_current_job()

        if job is not None:
            retry_intervals = final_results_retry_intervals()
            get_final_results_queue().enqueue_call(
                func=store_final_result_job,
                args=(job.id, completed_result),
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
                        workflow_query,
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
        "query": workflow_query,
        "attachments": normalized_attachments,
        "final_answer": final_answer_data,
        "execution": execution,
    }
