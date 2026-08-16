import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage, HumanMessage

from graph.state import YouTubeAnalysisResult, YouTubeClaim
from utils.token_usage import empty_token_usage


class YouTubeAgentTest(unittest.TestCase):
    @patch("agents.youtube_agent.agent.get_youtube_settings")
    @patch("agents.youtube_agent.agent.load_prompt", return_value="Prompt de vídeo")
    @patch("agents.youtube_agent.agent.youtube_llm")
    def test_analyzes_public_video_and_prepares_search_context(
        self,
        youtube_llm: Mock,
        load_prompt: Mock,
        get_youtube_settings: Mock,
    ) -> None:
        from agents.youtube_agent import query_youtube

        get_youtube_settings.return_value = SimpleNamespace(provider="google")
        structured_llm = youtube_llm.with_structured_output.return_value
        structured_llm.invoke.return_value = {
            "parsed": YouTubeAnalysisResult(
                summary="Vídeo sobre uma alegação de saúde.",
                claims=[YouTubeClaim(
                    timestamp="03:42",
                    claim="Uma vacina causa determinada doença.",
                    spoken_excerpt="A vacina provoca a doença.",
                    visual_context="Uma tabela é exibida na tela.",
                )],
                research_query="vacina doença evidências oficiais",
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
        self.assertEqual(messages[1].content[1], {
            "type": "media",
            "file_uri": "https://www.youtube.com/watch?v=video-id",
            "mime_type": "video/mp4",
        })
        context = result["media_contexts"][0]
        self.assertEqual(context["source"], "youtube_agent")
        self.assertIn("03:42", context["result"])
        self.assertIn("Uma vacina causa", context["result"])
        self.assertEqual(result["model_usage"][0]["role"], "youtube")
        load_prompt.assert_called_once()

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
