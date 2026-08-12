import logging
import os
from time import perf_counter

from langchain_core.tracers.langchain import wait_for_all_tracers
from rq import get_current_job

from jobs.execution_metadata import build_execution_metadata
from reanalysis.graph.workflow import reanalysis_workflow
from reanalysis.schemas import PanelFinalResult
from utils.token_usage import TOKEN_USAGE_FIELDS, empty_token_usage


logger = logging.getLogger(__name__)


def process_reanalyze_job(
    reanalysis_id: str,
    final_result_data: dict,
    prompt: str,
) -> dict:
    job = get_current_job()
    task_id = job.id if job is not None else None
    try:
        return _process_reanalyze_job(
            reanalysis_id,
            final_result_data,
            prompt,
            task_id=task_id,
        )
    finally:
        if job is not None:
            try:
                wait_for_all_tracers()
            except Exception:
                logger.exception(
                    "Falha ao finalizar traces da reanálise no LangSmith."
                )


def _process_reanalyze_job(
    reanalysis_id: str,
    final_result_data: dict,
    prompt: str,
    *,
    task_id: str | None = None,
) -> dict:
    started_at = perf_counter()
    original = PanelFinalResult.model_validate(final_result_data)
    final_answer = None
    executed_agents = set()
    executed_tools = set()
    usage_by_role = {
        role: empty_token_usage()
        for role in ("router", "search", "image")
    }

    for chunk in reanalysis_workflow.stream(
        {
            "query": original.query,
            "prompt": prompt,
            "attachments": original.attachments,
            "original_final_answer": original.to_final_answer(),
        },
        config={
            "run_name": "reanalysis_workflow",
            "tags": ["flow:reanalysis"],
            "metadata": {
                "task_id": task_id,
                "reanalysis_id": reanalysis_id,
                "app_version": os.getenv("APP_VERSION", "0.0.1"),
            },
        },
        stream_mode="updates",
    ):
        for step, data in chunk.items():
            if step in {
                "search_agent",
                "transcription_agent",
                "image_agent",
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

    if final_answer is None:
        raise RuntimeError("O workflow de reanálise não produziu resposta final.")

    execution = build_execution_metadata(
        started_at=started_at,
        usage_by_role=usage_by_role,
        executed_agents=executed_agents,
        executed_tools=executed_tools,
    )
    return {
        "status": "done",
        "result": {
            "reanalysis_id": reanalysis_id,
            "final_result_id": str(original.id),
            "prompt": prompt,
            "final_answer": final_answer.model_dump(mode="json"),
        },
        "execution": execution,
        "error": None,
    }
