import os
import unittest
from unittest.mock import Mock, patch

from langchain_core.messages import HumanMessage

from graph.state import FinalAnswerResult, ImageAnalysisResult


class ImageAgentTest(unittest.TestCase):
    @patch("agents.image_agent.load_prompt", return_value="Prompt visual")
    @patch("agents.image_agent.image_llm")
    def test_analyzes_image_and_prepares_search_query(
        self,
        image_llm: Mock,
        load_prompt: Mock,
    ) -> None:
        from agents.image_agent import query_image

        structured_llm = image_llm.with_structured_output.return_value
        structured_llm.invoke.return_value = ImageAnalysisResult(
            visible_text="Vacina causa doença",
            visual_context="Captura de uma publicação em rede social.",
            claims=["Uma vacina causa determinada doença."],
            research_query="vacina causa doença evidências oficiais",
        )

        result = query_image({
            "query": "Analise esta imagem",
            "attachment": {
                "type": "image",
                "url": "https://example.com/publicacao.jpg",
                "origin": "payload",
            },
        })

        image_llm.with_structured_output.assert_called_once_with(
            ImageAnalysisResult
        )
        messages = structured_llm.invoke.call_args.args[0]
        self.assertIsInstance(messages[1], HumanMessage)
        self.assertEqual(
            messages[1].content[1],
            {
                "type": "image_url",
                "image_url": {
                    "url": "https://example.com/publicacao.jpg"
                },
            },
        )
        context = result["media_contexts"][0]
        self.assertIn("Vacina causa doença", context["result"])
        self.assertIn(
            "vacina causa doença evidências oficiais",
            context["result"],
        )
        self.assertEqual(context["source"], "image_agent")
        load_prompt.assert_called_once()

    def test_rejects_non_image_attachment(self) -> None:
        from agents.image_agent import query_image

        with self.assertRaisesRegex(ValueError, "attachment inválido"):
            query_image({
                "query": "Analise este áudio",
                "attachment": {
                    "type": "audio",
                    "url": "https://example.com/audio.ogg",
                },
            })

    @patch.dict(
        os.environ,
        {
            "QDRANT_ENABLED": "false",
            "IMAGE_PROVIDER": "google",
            "IMAGE_MODEL": "gemini-image-test",
        },
    )
    @patch("jobs.get_final_results_queue")
    @patch("jobs.get_current_job", return_value=None)
    @patch("jobs.workflow.stream")
    def test_job_records_image_agent_and_model_only_when_executed(
        self,
        stream: Mock,
        get_current_job: Mock,
        get_final_results_queue: Mock,
    ) -> None:
        from jobs import process_analyze_job

        stream.return_value = [
            {
                "image_agent": {
                    "query": "Alegação extraída",
                    "results": [],
                }
            },
            {
                "search_agent": {
                    "results": [],
                    "tools": ["get_links", "fetch_url"],
                }
            },
            {
                "synthesize": {
                    "final_answer": FinalAnswerResult(
                        answer="Resposta",
                        sources=[],
                    )
                }
            },
        ]

        result = process_analyze_job(
            "Analise esta imagem",
            [{
                "type": "image",
                "url": "https://example.com/imagem.jpg",
            }],
        )

        self.assertEqual(
            result["execution"]["agents"],
            ["image_agent", "search_agent"],
        )
        self.assertIn(
            {
                "role": "image",
                "provider": "google",
                "model": "gemini-image-test",
            },
            result["execution"]["models"],
        )
        self.assertEqual(
            result["execution"]["tools"],
            ["fetch_url", "get_links"],
        )
        self.assertEqual(result["attachments"][0]["type"], "image")
        get_current_job.assert_called_once()
        get_final_results_queue.assert_not_called()


if __name__ == "__main__":
    unittest.main()
