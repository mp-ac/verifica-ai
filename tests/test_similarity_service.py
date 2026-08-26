import os
import unittest
from unittest.mock import Mock, patch

from similarity.client import SemanticRetrieverError
from similarity.schemas import (
    DuplicateAnalysisDecision,
    DuplicateAnalysisJudgeResult,
    RetrievedCandidate,
)
from utils.token_usage import empty_token_usage


def _retrieved_candidate(
    *,
    candidate_id: str = "candidate-1",
    match_type: str = "semantic",
    score: float | None = 12.5,
) -> RetrievedCandidate:
    """Build one generic retrieved candidate for tests."""
    return RetrievedCandidate(
        id=candidate_id,
        match_type=match_type,
        rank=1,
        score=score,
        text="Pergunta e título genéricos",
    )


@patch.dict(os.environ, {"SEMANTIC_RETRIEVER_ENABLED": "true"})
class SimilarityServiceTest(unittest.TestCase):
    @patch.dict(os.environ, {"SEMANTIC_RETRIEVER_ENABLED": "false"})
    @patch("similarity.service.retrieve_candidates")
    def test_disabled_retrieval_is_skipped(
        self,
        retrieve_candidates: Mock,
    ) -> None:
        from similarity.service import check_duplicate_analysis

        result = check_duplicate_analysis("Consulta genérica")

        self.assertEqual(result.outcome, "skipped")
        retrieve_candidates.assert_not_called()

    @patch("similarity.service.retrieve_candidates")
    def test_exact_url_match_skips_llm(
        self,
        retrieve_candidates: Mock,
    ) -> None:
        from similarity.service import check_duplicate_analysis

        retrieve_candidates.return_value = [
            _retrieved_candidate(match_type="exact_url", score=None)
        ]

        with patch("similarity.service.judge_duplicate_analysis") as judge:
            result = check_duplicate_analysis("https://example.test/item")

        self.assertEqual(result.outcome, "exact_match")
        self.assertEqual(result.candidate_id, "candidate-1")
        judge.assert_not_called()

    @patch("similarity.service.judge_duplicate_analysis")
    @patch("similarity.service.retrieve_candidates")
    def test_high_confidence_match_is_selected(
        self,
        retrieve_candidates: Mock,
        judge: Mock,
    ) -> None:
        from similarity.service import check_duplicate_analysis

        retrieve_candidates.return_value = [_retrieved_candidate()]
        judge.return_value = DuplicateAnalysisJudgeResult(
            evaluation=DuplicateAnalysisDecision(
                decision="match",
                candidate_id="candidate-1",
                confidence="high",
                reason="As alegações são equivalentes.",
            ),
            model_usage=empty_token_usage(),
        )

        result = check_duplicate_analysis("Consulta genérica")

        self.assertEqual(result.outcome, "match")
        self.assertEqual(result.candidate_id, "candidate-1")
        self.assertEqual(judge.call_args.args[0], "Consulta genérica")

    @patch("similarity.service.judge_duplicate_analysis")
    @patch("similarity.service.retrieve_candidates")
    def test_non_high_match_requires_review(
        self,
        retrieve_candidates: Mock,
        judge: Mock,
    ) -> None:
        from similarity.service import check_duplicate_analysis

        retrieve_candidates.return_value = [_retrieved_candidate()]
        judge.return_value = DuplicateAnalysisJudgeResult(
            evaluation=DuplicateAnalysisDecision(
                decision="match",
                candidate_id="candidate-1",
                confidence="medium",
                reason="Pode haver diferença de contexto.",
            ),
            model_usage=empty_token_usage(),
        )

        result = check_duplicate_analysis("Consulta genérica")

        self.assertEqual(result.outcome, "uncertain")
        self.assertEqual(result.candidate_id, "candidate-1")

    @patch("similarity.service.retrieve_candidates", return_value=[])
    def test_empty_result_continues_as_no_match(
        self,
        _retrieve_candidates: Mock,
    ) -> None:
        from similarity.service import check_duplicate_analysis

        result = check_duplicate_analysis("Consulta genérica")

        self.assertEqual(result.outcome, "no_match")

    @patch("similarity.service.retrieve_candidates")
    def test_retriever_failure_is_fail_open(
        self,
        retrieve_candidates: Mock,
    ) -> None:
        from similarity.service import check_duplicate_analysis

        retrieve_candidates.side_effect = SemanticRetrieverError("indisponível")

        with self.assertLogs("similarity.service", level="WARNING"):
            result = check_duplicate_analysis("Consulta genérica")

        self.assertEqual(result.outcome, "unavailable")
        self.assertEqual(result.failure_stage, "retriever")

    @patch("similarity.service.judge_duplicate_analysis")
    @patch("similarity.service.retrieve_candidates")
    def test_judge_failure_is_fail_open(
        self,
        retrieve_candidates: Mock,
        judge: Mock,
    ) -> None:
        from similarity.service import check_duplicate_analysis

        retrieve_candidates.return_value = [_retrieved_candidate()]
        judge.side_effect = RuntimeError("falha simulada")

        with self.assertLogs("similarity.service", level="WARNING"):
            result = check_duplicate_analysis("Consulta genérica")

        self.assertEqual(result.outcome, "unavailable")
        self.assertEqual(result.failure_stage, "judge")
        self.assertEqual(len(result.candidates), 1)

    @patch("similarity.service.retrieve_candidates")
    def test_explicit_attachments_skip_retrieval(
        self,
        retrieve_candidates: Mock,
    ) -> None:
        from similarity.service import check_duplicate_analysis

        result = check_duplicate_analysis(
            "Consulta genérica",
            explicit_attachments=[{"type": "image"}],
        )

        self.assertEqual(result.outcome, "skipped")
        retrieve_candidates.assert_not_called()


if __name__ == "__main__":
    unittest.main()
