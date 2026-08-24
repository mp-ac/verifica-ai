import json
from collections.abc import Iterable

from langchain_core.messages import HumanMessage

from config import DUPLICATE_ANALYSIS_JUDGE_PROMPT
from llm_registry import duplicate_judge_llm
from similarity.schemas import (
    DuplicateAnalysisDecision,
    DuplicateAnalysisJudgeResult,
    DuplicateCandidate,
)
from utils.prompts_util import load_prompt
from utils.token_usage import get_token_usage


def judge_duplicate_analysis(
    query: str,
    candidates: Iterable[DuplicateCandidate | dict],
) -> DuplicateAnalysisJudgeResult:
    """Decide whether up to three semantic candidates match one query."""
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("A consulta original não pode estar vazia.")

    normalized_candidates = [
        DuplicateCandidate.model_validate(candidate)
        for candidate in candidates
    ]
    if not 1 <= len(normalized_candidates) <= 3:
        raise ValueError("Informe entre um e três candidatos semânticos.")

    structured_llm = duplicate_judge_llm.with_structured_output(
        DuplicateAnalysisDecision,
        include_raw=True,
    )
    response = structured_llm.invoke([
        {
            "role": "system",
            "content": load_prompt(DUPLICATE_ANALYSIS_JUDGE_PROMPT),
        },
        HumanMessage(
            content=_build_evaluation_message(
                normalized_query,
                normalized_candidates,
            )
        ),
    ])
    if response["parsing_error"] is not None:
        raise response["parsing_error"]

    evaluation = DuplicateAnalysisDecision.model_validate(response["parsed"])
    _validate_selected_candidate(evaluation, normalized_candidates)

    return DuplicateAnalysisJudgeResult(
        evaluation=evaluation,
        model_usage=get_token_usage([response["raw"]]),
    )


def _build_evaluation_message(
    query: str,
    candidates: list[DuplicateCandidate],
) -> str:
    """Serialize the query and candidates without altering their content."""
    payload = {
        "original_query": query,
        "candidates": [
            candidate.model_dump()
            for candidate in candidates
        ],
    }
    return (
        "Avalie os dados JSON abaixo conforme as instruções do sistema.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def _validate_selected_candidate(
    evaluation: DuplicateAnalysisDecision,
    candidates: list[DuplicateCandidate],
) -> None:
    """Reject a candidate ID that was not supplied to the evaluator."""
    if evaluation.candidate_id is None:
        return

    candidate_ids = {candidate.id for candidate in candidates}
    if evaluation.candidate_id not in candidate_ids:
        raise ValueError(
            "O avaliador retornou um candidate_id que não foi fornecido."
        )
