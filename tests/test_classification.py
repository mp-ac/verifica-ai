import unittest

from pydantic import ValidationError

from graph.state import FinalAnswerResult


class ClassificationTest(unittest.TestCase):
    def _result(self, classification=None) -> FinalAnswerResult:
        return FinalAnswerResult(
            title="Resultado",
            answer="Resposta",
            classification=classification,
        )

    def test_supported_verdicts_are_classified(self) -> None:
        for verdict in (
            "verdadeiro",
            "falso",
            "enganoso",
            "inconclusivo",
        ):
            result = self._result(verdict)

            self.assertTrue(result.is_classified)
            self.assertEqual(result.model_dump()["classification"], verdict)

    def test_missing_verdict_is_not_classified(self) -> None:
        result = self._result()

        self.assertFalse(result.is_classified)
        self.assertIsNone(result.model_dump()["classification"])

    def test_unknown_verdict_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self._result("parcial")


if __name__ == "__main__":
    unittest.main()
