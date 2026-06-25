from graph.workflow import workflow


def process_analyze_job(query: str) -> dict:
    final_answer = None

    for chunk in workflow.stream({"query": query}, stream_mode="updates"):
        for _step, data in chunk.items():
            answer = data.get("final_answer")
            if answer is not None:
                final_answer = answer

    return {
        "status": "done",
        "query": query,
        "final_answer": final_answer.model_dump()
        if final_answer is not None else None,
    }
