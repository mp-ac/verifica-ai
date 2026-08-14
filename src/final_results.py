import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from langchain_core.tracers.langchain import wait_for_all_tracers
from langsmith import trace
import requests
from rq import get_current_job


load_dotenv()
load_dotenv(".env.painel-api")

logger = logging.getLogger(__name__)

_VALIDATION_ERROR_FIELD_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,200}$")
_VALIDATION_ERROR_FIELDS_LIMIT = 25


def final_results_api_url() -> str:
    return os.getenv("FINAL_RESULTS_API_URL", "").strip()


def final_results_api_token() -> str:
    return os.getenv("FINAL_RESULTS_API_TOKEN", "").strip()


def final_results_api_timeout_seconds() -> float:
    return float(os.getenv("FINAL_RESULTS_API_TIMEOUT_SECONDS", "15"))


def store_final_result_job(
    task_id: str,
    final_result: dict[str, Any],
) -> None:
    job = get_current_job()
    try:
        _store_final_result(task_id, final_result, job=job)
    finally:
        if job is not None:
            try:
                wait_for_all_tracers()
            except Exception:
                logger.exception(
                    "Falha ao finalizar trace de entrega ao painel."
                )


def _store_final_result(
    task_id: str,
    final_result: dict[str, Any],
    *,
    job: Any = None,
) -> None:
    api_url = final_results_api_url()
    api_token = final_results_api_token()

    if not api_url:
        raise RuntimeError("FINAL_RESULTS_API_URL nao foi configurada.")
    if not api_token:
        raise RuntimeError("FINAL_RESULTS_API_TOKEN nao foi configurado.")

    started_at = datetime.now(timezone.utc)
    try:
        response = requests.post(
            api_url,
            json={
                "task_id": task_id,
                **final_result,
            },
            headers={
                "Authorization": f"Bearer {api_token}",
                "Accept": "application/json",
            },
            timeout=final_results_api_timeout_seconds(),
        )
    except requests.RequestException as exc:
        _trace_panel_delivery(
            task_id,
            job=job,
            started_at=started_at,
            acknowledged=False,
            error=type(exc).__name__,
        )
        raise

    _trace_panel_delivery(
        task_id,
        job=job,
        started_at=started_at,
        acknowledged=response.ok,
        http_status=response.status_code,
        error=None if response.ok else f"HTTP {response.status_code}",
        validation_error_fields=_validation_error_fields(response),
    )
    response.raise_for_status()


def _validation_error_fields(response: requests.Response) -> list[str]:
    """Return only safe field paths from a panel validation response."""
    if response.status_code != 422:
        return []

    try:
        response_data = response.json()
    except (requests.JSONDecodeError, ValueError):
        return []

    if not isinstance(response_data, dict):
        return []

    errors = response_data.get("errors")
    if not isinstance(errors, dict):
        return []

    fields = {
        field
        for field in errors
        if isinstance(field, str)
        and _VALIDATION_ERROR_FIELD_PATTERN.fullmatch(field)
    }
    return sorted(fields)[:_VALIDATION_ERROR_FIELDS_LIMIT]


def _trace_panel_delivery(
    task_id: str,
    *,
    job: Any,
    started_at: datetime,
    acknowledged: bool,
    http_status: int | None = None,
    error: str | None = None,
    validation_error_fields: list[str] | None = None,
) -> None:
    try:
        with trace(
            "verificaai_painel_delivery",
            inputs={"task_id": task_id},
            tags=["flow:panel_delivery"],
            metadata={
                "task_id": task_id,
                "app_version": os.getenv("APP_VERSION", "0.0.1"),
                "rq_job_id": getattr(job, "id", None),
                "rq_retries_left": getattr(job, "retries_left", None),
            },
            parent="ignore",
            start_time=started_at,
        ) as run:
            outputs = {
                "acknowledged": acknowledged,
                "http_status": http_status,
            }
            if http_status == 422:
                outputs["failure_type"] = "validation_error"
                outputs["validation_error_fields"] = (
                    validation_error_fields or []
                )

            run.end(
                outputs=outputs,
                error=error,
            )
    except Exception:
        logger.exception("Falha ao registrar trace de entrega ao painel.")
