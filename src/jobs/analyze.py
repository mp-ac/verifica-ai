import logging
import os
from time import perf_counter

from langchain_core.tracers.langchain import wait_for_all_tracers
from rq import get_current_job

from config import ATTACHMENTS_MAX_ITEMS
from graph.workflow import workflow
from jobs.execution_metadata import build_execution_metadata
from jobs.result_dispatch import dispatch_completed_result
from utils.attachments import normalize_attachments
from utils.token_usage import TOKEN_USAGE_FIELDS, empty_token_usage


logger = logging.getLogger(__name__)


def process_analyze_job(
    query: str | None,
    attachments: list[dict] | None = None,
    requester: dict | None = None,
) -> dict:
    job = get_current_job()
    task_id = job.id if job is not None else None
    try:
        return _process_analyze_job(
            query,
            attachments,
            requester,
            task_id=task_id,
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
        config={
            "run_name": "analyze_workflow",
            "tags": ["flow:analyze"],
            "metadata": {
                "task_id": task_id,
                "app_version": os.getenv("APP_VERSION", "0.0.1"),
            },
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

    final_answer_data = (
        final_answer.model_dump() if final_answer is not None else None
    )
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
        )

    return {
        "status": "done",
        "query": workflow_query,
        "attachments": normalized_attachments,
        "final_answer": final_answer_data,
        "execution": execution,
    }
