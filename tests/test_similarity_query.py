import unittest

from graph.state import FinalAnswerResult
from similarity.query import build_duplicate_check_query


class SimilarityQueryTest(unittest.TestCase):
    def test_uses_final_title_without_classification_prefix(self) -> None:
        final_answer = FinalAnswerResult(
            title="ENGANOSO: Vacina altera o DNA humano",
            answer="Resposta final",
            classification="enganoso",
        )

        self.assertEqual(
            build_duplicate_check_query(final_answer),
            "Vacina altera o DNA humano",
        )

    def test_returns_none_without_final_answer(self) -> None:
        self.assertIsNone(build_duplicate_check_query(None))

    def test_returns_none_for_title_containing_only_verdict(self) -> None:
        final_answer = FinalAnswerResult(
            title="FALSO:",
            answer="Resposta final",
            classification="falso",
        )

        self.assertIsNone(build_duplicate_check_query(final_answer))


if __name__ == "__main__":
    unittest.main()
