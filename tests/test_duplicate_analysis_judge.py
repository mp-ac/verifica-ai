import json
import unittest
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage, HumanMessage

from similarity.schemas import (
    DuplicateAnalysisDecision,
    DuplicateCandidate,
)


def _candidate(
    candidate_id: str = "candidate-1",
    *,
    rank: int = 1,
    score: float = 12.5,
    text: str = "Pergunta: Uma alegação genérica. Título: Alegação genérica",
) -> DuplicateCandidate:
    """Build one generic semantic candidate for tests."""
    return DuplicateCandidate(
        id=candidate_id,
        rank=rank,
        score=score,
        text=text,
    )


class DuplicateAnalysisJudgeTest(unittest.TestCase):
    @patch("similarity.judge.load_prompt", return_value="Prompt do avaliador")
    @patch("similarity.judge.duplicate_judge_llm")
    def test_evaluates_candidates_with_scores_and_structured_output(
        self,
        duplicate_judge_llm: Mock,
        load_prompt: Mock,
    ) -> None:
        from similarity.judge import judge_duplicate_analysis

        structured_llm = (
            duplicate_judge_llm.with_structured_output.return_value
        )
        structured_llm.invoke.return_value = {
            "parsed": DuplicateAnalysisDecision(
                decision="match",
                candidate_id="candidate-1",
                confidence="high",
                reason="As consultas apresentam a mesma alegação.",
            ),
            "raw": AIMessage(content="", usage_metadata={
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
            }),
            "parsing_error": None,
        }

        result = judge_duplicate_analysis(
            "A afirmação genérica aconteceu?",
            [_candidate()],
        )

        duplicate_judge_llm.with_structured_output.assert_called_once_with(
            DuplicateAnalysisDecision,
            include_raw=True,
        )
        messages = structured_llm.invoke.call_args.args[0]
        self.assertIsInstance(messages[1], HumanMessage)
        payload = json.loads(messages[1].content.split("\n\n", 1)[1])
        self.assertEqual(
            payload["original_query"],
            "A afirmação genérica aconteceu?",
        )
        self.assertEqual(payload["candidates"][0]["score"], 12.5)
        self.assertEqual(result.evaluation.candidate_id, "candidate-1")
        self.assertEqual(result.model_usage["total_tokens"], 120)
        load_prompt.assert_called_once()

    @patch("similarity.judge.load_prompt", return_value="Prompt do avaliador")
    @patch("similarity.judge.duplicate_judge_llm")
    def test_accepts_explicit_no_match(
        self,
        duplicate_judge_llm: Mock,
        _load_prompt: Mock,
    ) -> None:
        from similarity.judge import judge_duplicate_analysis

        structured_llm = (
            duplicate_judge_llm.with_structured_output.return_value
        )
        structured_llm.invoke.return_value = {
            "parsed": DuplicateAnalysisDecision(
                decision="no_match",
                candidate_id=None,
                confidence="high",
                reason="Os candidatos tratam de alegações diferentes.",
            ),
            "raw": AIMessage(content=""),
            "parsing_error": None,
        }

        result = judge_duplicate_analysis(
            "Uma consulta genérica",
            [_candidate()],
        )

        self.assertEqual(result.evaluation.decision, "no_match")
        self.assertIsNone(result.evaluation.candidate_id)

    @patch("similarity.judge.load_prompt", return_value="Prompt do avaliador")
    @patch("similarity.judge.duplicate_judge_llm")
    def test_rejects_candidate_id_not_present_in_input(
        self,
        duplicate_judge_llm: Mock,
        _load_prompt: Mock,
    ) -> None:
        from similarity.judge import judge_duplicate_analysis

        structured_llm = (
            duplicate_judge_llm.with_structured_output.return_value
        )
        structured_llm.invoke.return_value = {
            "parsed": DuplicateAnalysisDecision(
                decision="match",
                candidate_id="unknown-candidate",
                confidence="high",
                reason="Alegações equivalentes.",
            ),
            "raw": AIMessage(content=""),
            "parsing_error": None,
        }

        with self.assertRaisesRegex(ValueError, "não foi fornecido"):
            judge_duplicate_analysis(
                "Uma consulta genérica",
                [_candidate()],
            )

    def test_rejects_empty_query_or_invalid_candidate_count(self) -> None:
        from similarity.judge import judge_duplicate_analysis

        with self.assertRaisesRegex(ValueError, "não pode estar vazia"):
            judge_duplicate_analysis("  ", [_candidate()])

        with self.assertRaisesRegex(ValueError, "entre um e três"):
            judge_duplicate_analysis("Consulta genérica", [])

        with self.assertRaisesRegex(ValueError, "entre um e três"):
            judge_duplicate_analysis(
                "Consulta genérica",
                [
                    _candidate(f"candidate-{index}", rank=min(index, 3))
                    for index in range(1, 5)
                ],
            )


if __name__ == "__main__":
    unittest.main()
