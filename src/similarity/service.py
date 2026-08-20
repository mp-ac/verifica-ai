import logging
from collections.abc import Iterable

from similarity.client import (
    SemanticRetrieverError,
    retrieve_candidates,
    semantic_retriever_enabled,
)
from similarity.judge import judge_duplicate_analysis
from similarity.schemas import (
    DuplicateCandidate,
    DuplicateCheckResult,
    RetrievedCandidate,
)


logger = logging.getLogger(__name__)


def check_duplicate_analysis(
    query: str | None,
    explicit_attachments: Iterable[dict] = (),
) -> DuplicateCheckResult:
    """Retrieve and judge duplicates without blocking the normal workflow."""
    if not semantic_retriever_enabled():
        return DuplicateCheckResult(outcome="skipped")

    normalized_query = (query or "").strip()
    attachments = list(explicit_attachments)
    if not normalized_query or attachments:
        return DuplicateCheckResult(outcome="skipped")

    try:
        candidates = retrieve_candidates(normalized_query)
    except SemanticRetrieverError:
        logger.warning(
            "Verificação de duplicidade indisponível na etapa de recuperação."
        )
        return DuplicateCheckResult(
            outcome="unavailable",
            failure_stage="retriever",
        )

    exact_candidates = [
        candidate
        for candidate in candidates
        if candidate.match_type == "exact_url"
    ]
    if exact_candidates:
        selected_candidate = min(
            exact_candidates,
            key=lambda candidate: candidate.rank,
        )
        return DuplicateCheckResult(
            outcome="exact_match",
            candidate_id=selected_candidate.id,
            candidates=candidates,
        )

    semantic_candidates = [
        _as_duplicate_candidate(candidate)
        for candidate in candidates
        if candidate.match_type == "semantic"
    ]
    if not semantic_candidates:
        return DuplicateCheckResult(
            outcome="no_match",
            candidates=candidates,
        )

    try:
        judge_result = judge_duplicate_analysis(
            normalized_query,
            semantic_candidates,
        )
    except Exception:
        logger.warning(
            "Verificação de duplicidade indisponível na etapa de avaliação."
        )
        return DuplicateCheckResult(
            outcome="unavailable",
            candidates=candidates,
            failure_stage="judge",
        )

    evaluation = judge_result.evaluation
    if evaluation.decision == "match" and evaluation.confidence == "high":
        outcome = "match"
        candidate_id = evaluation.candidate_id
    elif evaluation.decision == "no_match":
        outcome = "no_match"
        candidate_id = None
    else:
        outcome = "uncertain"
        candidate_id = evaluation.candidate_id

    return DuplicateCheckResult(
        outcome=outcome,
        candidate_id=candidate_id,
        candidates=candidates,
        evaluation=evaluation,
        model_usage=judge_result.model_usage,
    )


def _as_duplicate_candidate(
    candidate: RetrievedCandidate,
) -> DuplicateCandidate:
    """Convert one semantic API result into the judge input schema."""
    return DuplicateCandidate(
        id=candidate.id,
        rank=candidate.rank,
        score=candidate.score,
        text=candidate.text,
    )
