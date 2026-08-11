from time import perf_counter

from jobs.execution_metadata import build_execution_metadata
from reanalysis.graph.workflow import reanalysis_workflow
from reanalysis.schemas import PanelFinalResult
from utils.token_usage import TOKEN_USAGE_FIELDS, empty_token_usage


def process_reanalyze_job(
    reanalysis_id: str,
    final_result_data: dict,
    prompt: str,
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
