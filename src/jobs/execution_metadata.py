import os
from datetime import datetime, timezone
from time import perf_counter

from llm_settings import get_image_settings, get_youtube_settings


def build_execution_metadata(
    *,
    started_at: float,
    usage_by_role: dict,
    executed_agents: set[str],
    executed_tools: set[str],
) -> dict:
    """
    Build metadata describing the models, resources and execution time used.
    """
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

    if {"image_agent", "image_authenticity_agent"} & executed_agents:
        image_settings = get_image_settings()
        execution_models.append(
            {
                "role": "image",
                "provider": image_settings.provider,
                "model": image_settings.model,
                "usage": usage_by_role["image"],
            }
        )

    if "youtube_agent" in executed_agents:
        youtube_settings = get_youtube_settings()
        execution_models.append(
            {
                "role": "youtube",
                "provider": youtube_settings.provider,
                "model": youtube_settings.model,
                "usage": usage_by_role["youtube"],
            }
        )

    return {
        "models": execution_models,
        "agents": sorted(executed_agents),
        "tools": sorted(executed_tools),
        "duration_ms": round((perf_counter() - started_at) * 1000),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "app_version": os.getenv("APP_VERSION", "0.0.1"),
    }
