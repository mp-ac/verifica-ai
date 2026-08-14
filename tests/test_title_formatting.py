import unittest

from utils.title_formatting import format_classified_title


class TitleFormattingTest(unittest.TestCase):
    def test_adds_prefix_for_each_classification(self) -> None:
        expected_prefixes = {
            "verdadeiro": "VERDADEIRO",
            "falso": "FALSO",
            "enganoso": "ENGANOSO",
            "inconclusivo": "INCONCLUSIVO",
        }

        for classification, prefix in expected_prefixes.items():
            with self.subTest(classification=classification):
                self.assertEqual(
                    format_classified_title("Alegação analisada", classification),
                    f"{prefix}: Alegação analisada",
                )

    def test_replaces_existing_prefix(self) -> None:
        self.assertEqual(
            format_classified_title(
                "#FALSO: Alegação analisada",
                "enganoso",
            ),
            "ENGANOSO: Alegação analisada",
        )

    def test_leaves_unclassified_title_without_prefix(self) -> None:
        self.assertEqual(
            format_classified_title("Contexto da solicitação", None),
            "Contexto da solicitação",
        )

    def test_removes_incorrect_prefix_from_unclassified_title(self) -> None:
        self.assertEqual(
            format_classified_title("FALSO: Contexto da solicitação", None),
            "Contexto da solicitação",
        )

    def test_keeps_verdict_format_when_title_is_empty(self) -> None:
        self.assertEqual(format_classified_title("", "falso"), "FALSO:")


if __name__ == "__main__":
    unittest.main()
