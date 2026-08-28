import logging
import os
from time import perf_counter

from langchain_core.tracers.langchain import wait_for_all_tracers
from rq import get_current_job

from config import ATTACHMENTS_MAX_ITEMS
from graph.workflow import workflow
from jobs.execution_metadata import build_execution_metadata
from jobs.result_dispatch import dispatch_completed_result
from observability.langsmith import sanitized_langsmith_tracing
from similarity.check import run_duplicate_check
from similarity.query import build_duplicate_check_query
from utils.attachments import normalize_attachments
from utils.token_usage import TOKEN_USAGE_FIELDS, empty_token_usage


logger = logging.getLogger(__name__)


def _retry_attempt(job) -> int:
    """Return zero initially and the retry number on later executions."""
    if job is None:
        return 0

    intervals = getattr(job, "retry_intervals", None) or []
    retries_left = getattr(job, "retries_left", None)
    if retries_left is None:
        return 0

    return max(len(intervals) - retries_left, 0)


def process_analyze_job(
    query: str | None,
    attachments: list[dict] | None = None,
    requester: dict | None = None,
) -> dict:
    job = get_current_job()
    task_id = job.id if job is not None else None
    retry_attempt = _retry_attempt(job)
    with sanitized_langsmith_tracing():
        try:
            return _process_analyze_job(
                query,
                attachments,
                requester,
                task_id=task_id,
                retry_attempt=retry_attempt,
            )
        finally:
            if job is not None:
                try:
                    wait_for_all_tracers()
                except Exception:
                    logger.exception("Falha ao finalizar traces do LangSmith.")


def _process_analyze_job(
    query: str | None,
    attachments: list[dict] | None = None,
    requester: dict | None = None,
    *,
    task_id: str | None = None,
    retry_attempt: int = 0,
) -> dict:
    started_at = perf_counter()
    normalized_attachments = normalize_attachments(
        query,
        attachments or [],
        max_items=ATTACHMENTS_MAX_ITEMS,
    )
    workflow_query = (query or "").strip() or "Conteúdo enviado para análise"
    final_answer = None
    human_response_required = False
    executed_agents = set()
    executed_tools = set()
    usage_by_role = {
        role: empty_token_usage()
        for role in ("router", "search", "image", "youtube")
    }

    is_retry = retry_attempt > 0
    trace_tags = ["flow:analyze"]
    if is_retry:
        trace_tags.append("retry")

    for chunk in workflow.stream(
        {
            "query": workflow_query,
            "attachments": normalized_attachments,
        },
        config={
            "run_name": (
                "analyze_workflow_retry"
                if is_retry
                else "analyze_workflow"
            ),
            "tags": trace_tags,
            "metadata": {
                "task_id": task_id,
                "app_version": os.getenv("APP_VERSION", "0.0.1"),
                "retry_attempt": retry_attempt,
                "is_retry": is_retry,
            },
        },
        stream_mode="updates",
    ):
        for step, data in chunk.items():
            if step in {
                "search_agent",
                "transcription_agent",
                "image_agent",
                "youtube_agent",
            }:
                executed_agents.add(step)

            executed_tools.update(data.get("tools", []))

            for model_usage in data.get("model_usage", []):
                role = model_usage["role"]
                for field in TOKEN_USAGE_FIELDS:
                    usage_by_role[role][field] += model_usage.get(field, 0)

            answer = data.get("final_answer")
            if answer is not None:
                final_answer = answer
            if data.get("human_response_required"):
                human_response_required = True

    final_answer_data = (
        final_answer.model_dump() if final_answer is not None else None
    )
    duplicate_check = run_duplicate_check(
        build_duplicate_check_query(final_answer),
        [],
        task_id=task_id,
        retry_attempt=retry_attempt,
    )
    duplicate_check_data = duplicate_check.to_summary().model_dump()
    execution = build_execution_metadata(
        started_at=started_at,
        usage_by_role=usage_by_role,
        executed_agents=executed_agents,
        executed_tools=executed_tools,
    )
    completed_result = {
        "status": "done",
        "result": {
            "query": workflow_query,
            "attachments": normalized_attachments,
            "final_answer": final_answer_data,
        },
        "duplicate_check": duplicate_check_data,
        "execution": execution,
        "error": None,
    }
    if requester is not None:
        completed_result["result"]["requester"] = requester

    if final_answer is not None:
        dispatch_completed_result(
            query=workflow_query,
            final_answer=final_answer,
            completed_result=completed_result,
            persist_to_qdrant=not human_response_required,
        )

    return {
        "status": "done",
        "query": workflow_query,
        "attachments": normalized_attachments,
        "final_answer": final_answer_data,
        "duplicate_check": duplicate_check_data,
        "execution": execution,
    }
