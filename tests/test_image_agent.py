import os
import unittest
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage, HumanMessage

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
        structured_llm.invoke.return_value = {
            "parsed": ImageAnalysisResult(
                visible_text="Vacina causa doença",
                visual_context="Captura de uma publicação em rede social.",
                claims=["Uma vacina causa determinada doença."],
                research_query="vacina causa doença evidências oficiais",
            ),
            "raw": AIMessage(content="", usage_metadata={
                "input_tokens": 120,
                "output_tokens": 35,
                "total_tokens": 155,
                "input_token_details": {"cache_read": 10},
                "output_token_details": {"reasoning": 15},
            }),
            "parsing_error": None,
        }

        result = query_image({
            "query": "Analise esta imagem",
            "attachment": {
                "type": "image",
                "url": "https://example.com/publicacao.jpg",
                "origin": "payload",
            },
        })

        image_llm.with_structured_output.assert_called_once_with(
            ImageAnalysisResult,
            include_raw=True,
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
        self.assertEqual(result["model_usage"], [{
            "role": "image",
            "input_tokens": 120,
            "output_tokens": 35,
            "thinking_tokens": 15,
            "cached_input_tokens": 10,
            "total_tokens": 155,
        }])
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
                    "model_usage": [{
                        "role": "image",
                        "input_tokens": 100,
                        "output_tokens": 20,
                        "thinking_tokens": 5,
                        "cached_input_tokens": 0,
                        "total_tokens": 120,
                    }],
                }
            },
            {
                "search_agent": {
                    "results": [],
                    "tools": ["get_links", "fetch_url"],
                    "model_usage": [
                        {
                            "role": "search",
                            "input_tokens": 300,
                            "output_tokens": 60,
                            "thinking_tokens": 20,
                            "cached_input_tokens": 0,
                            "total_tokens": 360,
                        },
                        {
                            "role": "search",
                            "input_tokens": 400,
                            "output_tokens": 80,
                            "thinking_tokens": 30,
                            "cached_input_tokens": 25,
                            "total_tokens": 480,
                        },
                    ],
                }
            },
            {
                "synthesize": {
                    "final_answer": FinalAnswerResult(
                        answer="Resposta",
                        sources=[],
                    ),
                    "model_usage": [{
                        "role": "router",
                        "input_tokens": 200,
                        "output_tokens": 40,
                        "thinking_tokens": 10,
                        "cached_input_tokens": 15,
                        "total_tokens": 240,
                    }],
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
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "thinking_tokens": 5,
                    "cached_input_tokens": 0,
                    "total_tokens": 120,
                },
            },
            result["execution"]["models"],
        )
        search_model = next(
            model
            for model in result["execution"]["models"]
            if model["role"] == "search"
        )
        self.assertEqual(search_model["usage"], {
            "input_tokens": 700,
            "output_tokens": 140,
            "thinking_tokens": 50,
            "cached_input_tokens": 25,
            "total_tokens": 840,
        })
        self.assertEqual(
            result["execution"]["tools"],
            ["fetch_url", "get_links"],
        )
        self.assertEqual(result["attachments"][0]["type"], "image")
        get_current_job.assert_called_once()
        get_final_results_queue.assert_not_called()


if __name__ == "__main__":
    unittest.main()
