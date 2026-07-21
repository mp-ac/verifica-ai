import os
from typing import Any

import requests


def final_results_api_url() -> str:
    return os.getenv("FINAL_RESULTS_API_URL", "").strip()


def final_results_api_token() -> str:
    return os.getenv("FINAL_RESULTS_API_TOKEN", "").strip()


def final_results_api_timeout_seconds() -> float:
    return float(os.getenv("FINAL_RESULTS_API_TIMEOUT_SECONDS", "15"))


def store_final_result_job(
    task_id: str,
    query: str,
    final_answer: dict[str, Any],
) -> None:
    api_url = final_results_api_url()
    api_token = final_results_api_token()

    if not api_url:
        raise RuntimeError("FINAL_RESULTS_API_URL nao foi configurada.")
    if not api_token:
        raise RuntimeError("FINAL_RESULTS_API_TOKEN nao foi configurado.")

    response = requests.post(
        api_url,
        json={
            "task_id": task_id,
            "query": query,
            "final_result": final_answer["answer"],
            "sources": final_answer.get("sources", []),
        },
        headers={
            "Authorization": f"Bearer {api_token}",
            "Accept": "application/json",
        },
        timeout=final_results_api_timeout_seconds(),
    )
    response.raise_for_status()
