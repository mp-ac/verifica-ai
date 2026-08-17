import unittest
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage, ToolMessage

from graph.state import SourceItem


def grounded_message(
    *,
    queries: list[str] | None = None,
    supports: list[dict] | None = None,
) -> AIMessage:
    return AIMessage(
        content="Resposta baseada na pesquisa.",
        response_metadata={
            "grounding_metadata": {
                "web_search_queries": queries or [],
                "grounding_chunks": [
                    {
                        "web": {
                            "title": "Fonte A",
                            "uri": "https://example.com/a",
                        }
                    },
                    {
                        "web": {
                            "title": "Fonte B",
                            "uri": "https://example.com/b",
                        }
                    },
                ],
                "grounding_supports": supports or [],
            }
        },
        usage_metadata={
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
        },
    )


class SearchAgentTest(unittest.TestCase):
    def test_google_mode_registers_only_native_search(self) -> None:
        from agents.search_agent import tools as module

        with (
            patch.object(module, "SEARCH_GOOGLE_SEARCH_ENABLED", True),
            patch.object(module, "SEARCH_PROVIDER", "google"),
        ):
            self.assertEqual(module.get_search_tools(), [{"google_search": {}}])

    def test_google_mode_rejects_non_google_provider(self) -> None:
        from agents.search_agent import tools as module

        with (
            patch.object(module, "SEARCH_GOOGLE_SEARCH_ENABLED", True),
            patch.object(module, "SEARCH_PROVIDER", "openai"),
        ):
            with self.assertRaisesRegex(ValueError, "SEARCH_PROVIDER=google"):
                module.get_search_tools()

    def test_extracts_only_sources_referenced_by_grounding_supports(self) -> None:
        from agents.search_agent.grounding import extract_grounded_sources

        message = grounded_message(
            queries=["consulta executada"],
            supports=[{"grounding_chunk_indices": [1]}],
        )

        self.assertEqual(
            extract_grounded_sources([message]),
            [SourceItem(title="Fonte B", url="https://example.com/b")],
        )

    def test_marks_google_search_only_with_execution_metadata(self) -> None:
        from agents.search_agent.observability import get_used_tools

        native_message = grounded_message(
            queries=["consulta executada"],
            supports=[{"grounding_chunk_indices": [0]}],
        )
        custom_tool_message = ToolMessage(
            content="resultado",
            name="fetch_url",
            tool_call_id="call-1",
        )

        self.assertEqual(
            get_used_tools([native_message, custom_tool_message]),
            ["fetch_url", "google_search"],
        )
        self.assertEqual(
            get_used_tools([grounded_message()]),
            [],
        )

    @patch("agents.search_agent.agent.search_agent")
    def test_returns_grounded_sources_and_execution_tool(
        self,
        search_agent: Mock,
    ) -> None:
        from agents.search_agent import agent as module

        search_agent.invoke.return_value = {
            "messages": [
                grounded_message(
                    queries=["consulta executada"],
                    supports=[{"grounding_chunk_indices": [0, 1]}],
                )
            ]
        }

        with (
            patch.object(module, "SEARCH_GOOGLE_SEARCH_ENABLED", True),
            patch.object(module, "SEARCH_PROVIDER", "google"),
        ):
            result = module.query_search({"query": "Verifique esta alegação"})

        search_agent.invoke.assert_called_once()
        self.assertEqual(result["tools"], ["google_search"])
        self.assertEqual(
            [source.url for source in result["sources"]],
            ["https://example.com/a", "https://example.com/b"],
        )
        self.assertIn("1 consulta(s)", result["debug_events"][1])

    @patch("agents.search_agent.agent.search_agent")
    def test_retries_when_first_google_response_has_no_grounding(
        self,
        search_agent: Mock,
    ) -> None:
        from agents.search_agent import agent as module

        search_agent.invoke.side_effect = [
            {"messages": [AIMessage(content="Resposta sem pesquisa")]},
            {
                "messages": [
                    grounded_message(
                        queries=["consulta executada"],
                        supports=[{"grounding_chunk_indices": [0]}],
                    )
                ]
            },
        ]

        with (
            patch.object(module, "SEARCH_GOOGLE_SEARCH_ENABLED", True),
            patch.object(module, "SEARCH_PROVIDER", "google"),
        ):
            result = module.query_search({"query": "Verifique esta alegação"})

        self.assertEqual(search_agent.invoke.call_count, 2)
        self.assertIn("repetiu a pesquisa", result["debug_events"][1])

    @patch("agents.search_agent.agent.search_agent")
    def test_fails_when_google_search_has_no_cited_sources(
        self,
        search_agent: Mock,
    ) -> None:
        from agents.search_agent import agent as module

        search_agent.invoke.return_value = {
            "messages": [grounded_message(queries=["consulta executada"])]
        }

        with (
            patch.object(module, "SEARCH_GOOGLE_SEARCH_ENABLED", True),
            patch.object(module, "SEARCH_PROVIDER", "google"),
        ):
            with self.assertRaisesRegex(
                module.IncompleteResearchError,
                "não citou fontes",
            ):
                module.query_search({"query": "Verifique esta alegação"})

        self.assertEqual(search_agent.invoke.call_count, 2)


if __name__ == "__main__":
    unittest.main()
