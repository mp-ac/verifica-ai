import unittest
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage

from image_authenticity import (
    ImageAuthenticityAnalysis,
    ImageAuthenticityModelResult,
    serialize_image_authenticity_analyses,
)


class ImageAuthenticityAgentTest(unittest.TestCase):
    def test_serializes_assessments_in_attachment_order(self) -> None:
        analyses = [
            ImageAuthenticityAnalysis(
                attachment_index=index,
                status="completed",
                assessment="inconclusive",
            )
            for index in (2, 0, 1)
        ]

        result = serialize_image_authenticity_analyses(analyses)

        self.assertEqual(
            [analysis["attachment_index"] for analysis in result],
            [0, 1, 2],
        )

    @patch(
        "agents.image_authenticity_agent.load_prompt",
        return_value="Prompt de autenticidade",
    )
    @patch("agents.image_authenticity_agent.image_llm")
    def test_returns_structured_assessment_for_one_attachment(
        self,
        image_llm: Mock,
        load_prompt: Mock,
    ) -> None:
        from agents.image_authenticity_agent import query_image_authenticity

        image_llm.with_structured_output.return_value.invoke.return_value = {
            "parsed": ImageAuthenticityModelResult(
                assessment="likely_ai_generated",
                confidence=0.82,
                signals=["Texturas excessivamente uniformes."],
                limitations=["A imagem pode ter sido recomprimida."],
            ),
            "raw": AIMessage(content="", usage_metadata={
                "input_tokens": 80,
                "output_tokens": 20,
                "total_tokens": 100,
            }),
            "parsing_error": None,
        }

        result = query_image_authenticity({
            "query": "Analise a imagem",
            "attachment_index": 2,
            "attachment": {
                "type": "image",
                "url": "https://example.com/imagem.jpg",
            },
        })

        analysis = result["image_authenticity_analyses"][0]
        self.assertEqual(analysis.attachment_index, 2)
        self.assertEqual(analysis.status, "completed")
        self.assertEqual(analysis.assessment, "likely_ai_generated")
        self.assertEqual(analysis.confidence, 0.82)
        self.assertEqual(analysis.method, "visual_model")
        self.assertEqual(result["model_usage"][0]["role"], "image")
        load_prompt.assert_called_once()

    @patch("agents.image_authenticity_agent.logger")
    @patch("agents.image_authenticity_agent.image_llm")
    def test_fails_open_without_logging_the_image_url(
        self,
        image_llm: Mock,
        logger: Mock,
    ) -> None:
        from agents.image_authenticity_agent import query_image_authenticity

        image_llm.with_structured_output.side_effect = RuntimeError(
            "provider unavailable"
        )

        result = query_image_authenticity({
            "query": "Analise a imagem",
            "attachment_index": 0,
            "attachment": {
                "type": "image",
                "url": "https://private.example.com/secret.jpg",
            },
        })

        analysis = result["image_authenticity_analyses"][0]
        self.assertEqual(analysis.status, "unavailable")
        self.assertEqual(analysis.assessment, "inconclusive")
        self.assertIsNone(analysis.confidence)
        self.assertNotIn("model_usage", result)
        self.assertNotIn(
            "private.example.com",
            str(logger.warning.call_args),
        )


if __name__ == "__main__":
    unittest.main()
