import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage, HumanMessage
from pydantic import ValidationError

from graph.state import (
    YouTubeAnalysisResult,
    YouTubeRelevantSegment,
)
from agents.youtube_agent.tools import YouTubeMetadata, YouTubeMetadataError
from utils.token_usage import empty_token_usage


class YouTubeAgentTest(unittest.TestCase):
    @patch("agents.youtube_agent.agent.get_youtube_metadata")
    @patch("agents.youtube_agent.agent.get_youtube_settings")
    @patch("agents.youtube_agent.agent.load_prompt", return_value="Prompt de vídeo")
    @patch("agents.youtube_agent.agent.youtube_llm")
    def test_analyzes_public_video_and_prepares_search_context(
        self,
        youtube_llm: Mock,
        load_prompt: Mock,
        get_youtube_settings: Mock,
        get_youtube_metadata: Mock,
    ) -> None:
        from agents.youtube_agent import query_youtube

        get_youtube_settings.return_value = SimpleNamespace(provider="google")
        get_youtube_metadata.return_value = YouTubeMetadata(
            title="ACABOU! VACINA CAUSA DETERMINADA DOENÇA #SAÚDE",
            thumbnail_url="https://i.ytimg.com/vi/video-id/hq2.jpg",
        )
        structured_llm = youtube_llm.with_structured_output.return_value
        structured_llm.invoke.return_value = {
            "parsed": YouTubeAnalysisResult(
                thumbnail_context="Uma tabela acompanha a chamada do título.",
                central_claim="Uma vacina causa determinada doença.",
                central_claim_source="video_title",
                relevant_segments=[YouTubeRelevantSegment(
                    timestamp="03:42",
                    spoken_excerpt="A vacina provoca a doença.",
                    visual_context="Uma tabela é exibida na tela.",
                    relevance="O trecho repete a alegação do título.",
                )],
                requires_clarification=False,
                limitations=["Texto pequeno parcialmente ilegível."],
            ),
            "raw": AIMessage(content="", usage_metadata={
                "input_tokens": 500,
                "output_tokens": 80,
                "total_tokens": 580,
                "output_token_details": {"reasoning": 20},
            }),
            "parsing_error": None,
        }

        result = query_youtube({
            "query": "Verifique as alegações deste vídeo",
            "attachment": {
                "type": "youtube",
                "url": "https://www.youtube.com/watch?v=video-id",
                "origin": "query",
            },
        })

        youtube_llm.with_structured_output.assert_called_once_with(
            YouTubeAnalysisResult,
            include_raw=True,
        )
        messages = structured_llm.invoke.call_args.args[0]
        self.assertIsInstance(messages[1], HumanMessage)
        self.assertIn(
            "ACABOU! VACINA CAUSA DETERMINADA DOENÇA",
            messages[1].content[0]["text"],
        )
        self.assertEqual(messages[1].content[1], {
            "type": "image_url",
            "image_url": {
                "url": "https://i.ytimg.com/vi/video-id/hq2.jpg",
            },
        })
        self.assertEqual(messages[1].content[2], {
            "type": "media",
            "file_uri": "https://www.youtube.com/watch?v=video-id",
            "mime_type": "video/mp4",
        })
        context = result["media_contexts"][0]
        self.assertEqual(context["source"], "youtube_agent")
        self.assertIn("03:42", context["result"])
        self.assertIn("Título oficial do vídeo", context["result"])
        self.assertIn("Contexto da thumbnail", context["result"])
        self.assertIn("Uma vacina causa", context["result"])
        self.assertNotIn("Plano prioritário de pesquisa", context["result"])
        self.assertEqual(
            result["youtube_central_claim"],
            "Uma vacina causa determinada doença.",
        )
        self.assertFalse(result["youtube_requires_clarification"])
        self.assertEqual(result["model_usage"][0]["role"], "youtube")
        self.assertIn("uma alegação central", result["debug_events"][1])
        load_prompt.assert_called_once()

    @patch("agents.youtube_agent.agent.get_youtube_metadata")
    @patch("agents.youtube_agent.agent.get_youtube_settings")
    @patch("agents.youtube_agent.agent.load_prompt", return_value="Prompt de vídeo")
    @patch("agents.youtube_agent.agent.youtube_llm")
    def test_does_not_accept_inferred_title_when_metadata_is_unavailable(
        self,
        youtube_llm: Mock,
        _load_prompt: Mock,
        get_youtube_settings: Mock,
        get_youtube_metadata: Mock,
    ) -> None:
        from agents.youtube_agent import query_youtube

        get_youtube_settings.return_value = SimpleNamespace(provider="google")
        get_youtube_metadata.side_effect = YouTubeMetadataError("indisponível")
        youtube_llm.with_structured_output.return_value.invoke.return_value = {
            "parsed": YouTubeAnalysisResult(
                central_claim="Uma ação contra Bolsonaro foi arquivada.",
                central_claim_source="video_title",
            ),
            "raw": AIMessage(content="", usage_metadata={
                "input_tokens": 20,
                "output_tokens": 10,
                "total_tokens": 30,
            }),
            "parsing_error": None,
        }

        result = query_youtube({
            "query": "https://www.youtube.com/watch?v=video-id",
            "attachment": {
                "type": "youtube",
                "url": "https://www.youtube.com/watch?v=video-id",
            },
        })

        self.assertTrue(result["youtube_requires_clarification"])
        self.assertNotIn("youtube_central_claim", result)
        self.assertIn("não puderam ser obtidos", result["media_contexts"][0]["result"])

    def test_prepare_search_uses_only_central_youtube_claim(self) -> None:
        from graph.nodes import prepare_search_query

        result = prepare_search_query({
            "query": "https://www.youtube.com/shorts/video-id",
            "attachments": [{
                "type": "youtube",
                "url": "https://www.youtube.com/shorts/video-id",
            }],
            "media_contexts": [{
                "source": "youtube_agent",
                "result": "Trecho do vídeo diretamente relacionado.",
            }, {
                "source": "image_agent",
                "result": "Texto relevante encontrado em outra imagem.",
            }],
            "youtube_central_claim": (
                "O arquivamento da ação absolveu o investigado."
            ),
            "youtube_requires_clarification": False,
        })

        research_query = result["research_query"]
        self.assertIn("O arquivamento da ação absolveu", research_query)
        self.assertIn("Trecho do vídeo diretamente relacionado", research_query)
        self.assertIn("Verifique exclusivamente", research_query)
        self.assertNotIn("youtube.com", research_query)
        self.assertIn("Texto relevante encontrado", research_query)

    def test_prepare_search_returns_clarification_without_query(self) -> None:
        from graph.nodes import prepare_search_query, route_after_prepare_search

        result = prepare_search_query({
            "query": "https://www.youtube.com/watch?v=video-id",
            "attachments": [],
            "media_contexts": [],
            "youtube_requires_clarification": True,
            "youtube_clarification_reason": (
                "O título é genérico e o vídeo reúne três notícias."
            ),
        })

        final_answer = result["final_answer"]
        self.assertIsNone(final_answer.classification)
        self.assertFalse(final_answer.is_classified)
        self.assertIn("indicar a afirmação", final_answer.answer)
        self.assertNotIn("research_query", result)
        self.assertEqual(
            route_after_prepare_search(result),
            "end",
        )

    def test_rejects_ambiguous_structured_result(self) -> None:
        with self.assertRaises(ValidationError):
            YouTubeAnalysisResult(
                central_claim="Uma das notícias é verdadeira.",
                central_claim_source="spoken_content",
                requires_clarification=True,
                clarification_reason="Há vários assuntos independentes.",
            )

    @patch("graph.nodes.router_llm")
    @patch("agents.search_agent.agent.search_agent")
    @patch("agents.youtube_agent.agent.get_youtube_metadata")
    @patch("agents.youtube_agent.agent.get_youtube_settings")
    @patch("agents.youtube_agent.agent.load_prompt", return_value="Prompt de vídeo")
    @patch("agents.youtube_agent.agent.youtube_llm")
    def test_workflow_skips_search_and_synthesis_when_video_needs_clarification(
        self,
        youtube_llm: Mock,
        _load_prompt: Mock,
        get_youtube_settings: Mock,
        get_youtube_metadata: Mock,
        search_agent: Mock,
        router_llm: Mock,
    ) -> None:
        from graph.workflow import workflow

        get_youtube_settings.return_value = SimpleNamespace(provider="google")
        get_youtube_metadata.return_value = YouTubeMetadata(
            title="Resumo de notícias",
            thumbnail_url="https://i.ytimg.com/vi/video-id/hq2.jpg",
        )
        youtube_llm.with_structured_output.return_value.invoke.return_value = {
            "parsed": YouTubeAnalysisResult(
                requires_clarification=True,
                clarification_reason=(
                    "O título não define uma alegação e há vários tópicos."
                ),
            ),
            "raw": AIMessage(content="", usage_metadata={
                "input_tokens": 20,
                "output_tokens": 10,
                "total_tokens": 30,
            }),
            "parsing_error": None,
        }

        state = workflow.invoke({
            "query": "https://www.youtube.com/watch?v=video-id",
            "attachments": [{
                "type": "youtube",
                "url": "https://www.youtube.com/watch?v=video-id",
                "origin": "query",
            }],
        })

        search_agent.invoke.assert_not_called()
        router_llm.with_structured_output.assert_not_called()
        self.assertIsNone(state["final_answer"].classification)
        self.assertIn("indicar a afirmação", state["final_answer"].answer)

    @patch("agents.youtube_agent.tools.metadata.requests.get")
    def test_fetches_official_youtube_metadata_without_api_key(
        self,
        requests_get: Mock,
    ) -> None:
        from agents.youtube_agent.tools.metadata import (
            YOUTUBE_METADATA_TIMEOUT_SECONDS,
            YOUTUBE_OEMBED_URL,
            get_youtube_metadata,
        )

        requests_get.return_value.json.return_value = {
            "title": "ACABOU! BOLSONARO ABSOLVIDO NA CPI DA COVID",
            "thumbnail_url": "https://i.ytimg.com/vi/video-id/hq2.jpg",
        }

        metadata = get_youtube_metadata(
            "https://www.youtube.com/shorts/video-id"
        )

        requests_get.assert_called_once_with(
            YOUTUBE_OEMBED_URL,
            params={
                "url": "https://www.youtube.com/shorts/video-id",
                "format": "json",
            },
            headers={"Accept": "application/json"},
            timeout=YOUTUBE_METADATA_TIMEOUT_SECONDS,
        )
        requests_get.return_value.raise_for_status.assert_called_once_with()
        self.assertEqual(
            metadata.title,
            "ACABOU! BOLSONARO ABSOLVIDO NA CPI DA COVID",
        )
        self.assertEqual(
            metadata.thumbnail_url,
            "https://i.ytimg.com/vi/video-id/hq2.jpg",
        )

    @patch("agents.youtube_agent.agent.get_youtube_settings")
    def test_requires_google_provider(self, get_youtube_settings: Mock) -> None:
        from agents.youtube_agent import query_youtube

        get_youtube_settings.return_value = SimpleNamespace(provider="openai")

        with self.assertRaisesRegex(ValueError, "provider google"):
            query_youtube({
                "query": "Analise",
                "attachment": {
                    "type": "youtube",
                    "url": "https://youtu.be/video-id",
                },
            })

    def test_routes_youtube_attachment_to_specialized_agent(self) -> None:
        from graph.nodes import classify_query

        result = classify_query({
            "query": "Analise o vídeo",
            "attachments": [{
                "type": "youtube",
                "url": "https://youtu.be/video-id",
                "origin": "query",
            }],
        })

        self.assertEqual(
            result["classifications"][0]["source"],
            "youtube_agent",
        )

    @patch("jobs.execution_metadata.get_youtube_settings")
    def test_records_youtube_model_only_when_agent_executes(
        self,
        get_youtube_settings: Mock,
    ) -> None:
        from jobs.execution_metadata import build_execution_metadata

        get_youtube_settings.return_value = SimpleNamespace(
            provider="google",
            model="gemini-2.5-flash",
        )
        usage_by_role = {
            role: empty_token_usage()
            for role in ("router", "search", "image", "youtube")
        }
        usage_by_role["youtube"]["total_tokens"] = 580

        execution = build_execution_metadata(
            started_at=0,
            usage_by_role=usage_by_role,
            executed_agents={"youtube_agent", "search_agent"},
            executed_tools={"google_search"},
        )

        youtube_model = next(
            model
            for model in execution["models"]
            if model["role"] == "youtube"
        )
        self.assertEqual(youtube_model["provider"], "google")
        self.assertEqual(youtube_model["model"], "gemini-2.5-flash")
        self.assertEqual(youtube_model["usage"]["total_tokens"], 580)


if __name__ == "__main__":
    unittest.main()
