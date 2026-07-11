from rq import get_current_job

from graph.workflow import workflow
from qdrant import try_save_final_answer


def process_analyze_job(query: str) -> dict:
    final_answer = None

    for chunk in workflow.stream({"query": query}, stream_mode="updates"):
        for _step, data in chunk.items():
            answer = data.get("final_answer")
            if answer is not None:
                final_answer = answer

    if final_answer is not None:
        job = get_current_job()
        try_save_final_answer(
            query=query,
            final_answer=final_answer,
            point_id=job.id if job is not None else None,
        )

    return {
        "status": "done",
        "query": query,
        "final_answer": final_answer.model_dump()
        if final_answer is not None else None,
    }
