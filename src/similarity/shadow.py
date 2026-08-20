import logging
import os
from datetime import datetime, timezone

from langsmith import trace

from similarity.schemas import DuplicateCheckResult
from similarity.service import check_duplicate_analysis


logger = logging.getLogger(__name__)


def _duplicate_check_trace_metadata(
    result: DuplicateCheckResult,
) -> dict:
    """Return a payload-free summary of one duplicate check."""
    metadata = {
        "duplicate_check_outcome": result.outcome,
        "candidate_count": len(result.candidates),
        "candidates": [
            {
                "id": candidate.id,
                "match_type": candidate.match_type,
                "rank": candidate.rank,
                "score": candidate.score,
            }
            for candidate in result.candidates
        ],
    }
    if result.candidate_id is not None:
        metadata["selected_candidate_id"] = result.candidate_id
    if result.evaluation is not None:
        metadata["judge_decision"] = result.evaluation.decision
        metadata["judge_confidence"] = result.evaluation.confidence
    if result.failure_stage is not None:
        metadata["failure_stage"] = result.failure_stage
    return metadata


def run_duplicate_check_shadow(
    query: str | None,
    attachments: list[dict],
    *,
    task_id: str | None,
    retry_attempt: int,
) -> None:
    """Trace duplicate detection without changing the analysis result."""
    try:
        with trace(
            "duplicate_check",
            inputs={"task_id": task_id},
            tags=["flow:duplicate_check", "mode:shadow"],
            metadata={
                "task_id": task_id,
                "app_version": os.getenv("APP_VERSION", "0.0.1"),
                "retry_attempt": retry_attempt,
                "shadow_mode": True,
            },
            parent="ignore",
            start_time=datetime.now(timezone.utc),
        ) as run:
            try:
                result = check_duplicate_analysis(query, attachments)
            except Exception as exc:
                run.add_metadata({
                    "duplicate_check_outcome": "unavailable",
                    "failure_stage": "worker",
                })
                run.end(
                    outputs={"completed": False},
                    error=type(exc).__name__,
                )
                logger.warning(
                    "Verificação de duplicidade falhou no modo sombra."
                )
                return

            run.add_metadata(_duplicate_check_trace_metadata(result))
            run.end(outputs={"completed": True})
    except Exception:
        logger.warning(
            "Falha ao registrar trace da verificação de duplicidade."
        )
