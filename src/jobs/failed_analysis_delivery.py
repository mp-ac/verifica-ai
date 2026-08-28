import logging
import os
from datetime import datetime, timezone
from typing import Any

from graph.state import FinalAnswerResult
from jobs.result_dispatch.panel import enqueue_panel_result


logger = logging.getLogger(__name__)


def _job_input(job: Any) -> tuple[str, list[dict], dict | None]:
    """Recover the original accepted input without invoking the workflow."""
    args = getattr(job, "args", ()) or ()
    query = args[0] if len(args) > 0 and isinstance(args[0], str) else ""
    attachments = args[1] if len(args) > 1 and isinstance(args[1], list) else []
    requester = args[2] if len(args) > 2 and isinstance(args[2], dict) else None
    return query.strip() or "Conteúdo enviado para análise", attachments, requester


def _failure_result(job: Any, error: str) -> dict:
    """Build a panel-compatible pending item for a terminal analysis failure."""
    query, attachments, requester = _job_input(job)
    final_answer = FinalAnswerResult(
        title="A análise automatizada falhou",
        answer=(
            "A análise automatizada não pôde ser concluída. A mensagem foi "
            "preservada para avaliação e resposta humana."
        ),
        sources=[],
        classification=None,
    )
    result = {
        "query": query,
        "attachments": attachments,
        "final_answer": final_answer.model_dump(),
    }
    if requester is not None:
        result["requester"] = requester

    return {
        "status": "done",
        "result": result,
        "execution": {
            "models": [],
            "agents": [],
            "tools": [],
            "duration_ms": 0,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "app_version": os.getenv("APP_VERSION", "0.0.1"),
        },
        "error": error or "A análise automatizada falhou.",
    }


def deliver_failed_analysis(
    job: Any,
    _connection: Any,
    _exception_type: type[BaseException],
    exception: BaseException,
    _traceback: Any,
) -> None:
    """Deliver only terminal failures; RQ invokes this before each retry too."""
    if getattr(job, "should_retry", False):
        return

    try:
        enqueue_panel_result(
            task_id=job.id,
            completed_result=_failure_result(job, str(exception)),
        )
    except Exception:
        logger.exception(
            "Falha ao preservar análise com erro no painel: task_id=%s",
            getattr(job, "id", None),
        )


def deliver_stopped_analysis(job: Any, _connection: Any) -> None:
    """Preserve an intentionally stopped analysis for human handling."""
    try:
        enqueue_panel_result(
            task_id=job.id,
            completed_result=_failure_result(
                job,
                "A execução da análise foi interrompida.",
            ),
        )
    except Exception:
        logger.exception(
            "Falha ao preservar análise interrompida no painel: task_id=%s",
            getattr(job, "id", None),
        )
