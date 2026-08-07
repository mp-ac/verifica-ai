import os
from datetime import datetime, timezone
from time import perf_counter

from config import ATTACHMENTS_MAX_ITEMS
from graph.workflow import workflow
from llm_settings import get_image_settings
from result_dispatch import dispatch_completed_result
from utils.attachments import normalize_attachments
from utils.token_usage import TOKEN_USAGE_FIELDS, empty_token_usage


def process_analyze_job(
    query: str | None,
    attachments: list[dict] | None = None,
    requester: dict | None = None,
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
