import unittest
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage

from graph.state import FinalAnswerResult, ImageAnalysisResult


class AttachmentWorkflowTest(unittest.TestCase):
    @patch("graph.nodes.load_prompt", return_value="Sintetize {query}")
    @patch("graph.nodes.router_llm")
    @patch("agents.search_agent.search_agent")
    @patch("agents.transcription_agent.transcription_agent")
    @patch("agents.image_agent.load_prompt", return_value="Prompt visual")
    @patch("agents.image_agent.image_llm")
    def test_processes_multiple_media_before_one_search(
        self,
        image_llm: Mock,
        image_load_prompt: Mock,
        transcription_agent: Mock,
        search_agent: Mock,
        router_llm: Mock,
        router_load_prompt: Mock,
    ) -> None:
        from graph.workflow import workflow

        image_llm.with_structured_output.return_value.invoke.return_value = {
            "parsed": ImageAnalysisResult(
                visible_text="Alegação na imagem",
                visual_context="Publicação em uma rede social.",
                claims=["A imagem apresenta uma alegação."],
                research_query="alegação imagem evidências",
            ),
            "raw": AIMessage(content="", usage_metadata={
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
            }),
            "parsing_error": None,
        }
        transcription_agent.invoke.side_effect = [
            {"messages": [AIMessage(content="Transcrição do áudio")]},
            {"messages": [AIMessage(content="Transcrição do vídeo")]},
        ]
        search_agent.invoke.return_value = {
            "messages": [AIMessage(content="Resultado da pesquisa")]
        }
        router_llm.with_structured_output.return_value.invoke.return_value = {
            "parsed": FinalAnswerResult(
                title="Conteúdos enviados e resultados da pesquisa",
                answer="Resposta consolidada",
                sources=[],
                classification="inconclusivo",
            ),
            "raw": AIMessage(content="", usage_metadata={
                "input_tokens": 200,
                "output_tokens": 40,
                "total_tokens": 240,
            }),
            "parsing_error": None,
        }

        state = workflow.invoke({
            "query": "Verifique os conteúdos enviados",
            "attachments": [
                {
                    "type": "image",
                    "url": "https://example.com/imagem.jpg",
                    "origin": "payload",
                },
                {
                    "type": "audio",
                    "url": "https://example.com/audio.ogg",
                    "origin": "payload",
                },
                {
                    "type": "video",
                    "url": "https://example.com/video.mp4",
                    "origin": "payload",
                },
            ],
        })

        self.assertEqual(len(state["media_contexts"]), 3)
        self.assertEqual(transcription_agent.invoke.call_count, 2)
        search_agent.invoke.assert_called_once()
        research_query = (
            search_agent.invoke.call_args.args[0]["messages"][0]["content"]
        )
        self.assertIn("Alegação na imagem", research_query)
        self.assertIn("Transcrição do áudio", research_query)
        self.assertIn("Transcrição do vídeo", research_query)
        self.assertEqual(state["final_answer"].answer, "Resposta consolidada")
        self.assertEqual(
            state["final_answer"].classification,
            "inconclusivo",
        )
        self.assertTrue(state["final_answer"].is_classified)
        self.assertEqual(
            state["final_answer"].title,
            "Conteúdos enviados e resultados da pesquisa",
        )
        self.assertEqual(len(state["model_usage"]), 5)
        image_load_prompt.assert_called_once()
        router_load_prompt.assert_called_once()


if __name__ == "__main__":
    unittest.main()
