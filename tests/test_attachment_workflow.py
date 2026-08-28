import unittest
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage

from graph.state import FinalAnswerResult, ImageAnalysisResult, SourceItem
from image_authenticity import ImageAuthenticityModelResult


class AttachmentWorkflowTest(unittest.TestCase):
    def test_routes_each_image_to_content_and_authenticity_agents(self) -> None:
        from graph.nodes import classify_query, route_to_agents

        classification = classify_query({
            "query": "Verifique as imagens",
            "attachments": [
                {
                    "type": "image",
                    "url": "https://example.com/primeira.jpg",
                },
                {
                    "type": "image",
                    "url": "https://example.com/segunda.jpg",
                },
            ],
        })
        sends = route_to_agents(classification)

        self.assertEqual(
            [(send.node, send.arg["attachment_index"]) for send in sends],
            [
                ("image_agent", 0),
                ("image_authenticity_agent", 0),
                ("image_agent", 1),
                ("image_authenticity_agent", 1),
            ],
        )

    @patch("graph.nodes.load_prompt", return_value="Sintetize {query}")
    @patch("graph.nodes.router_llm")
    def test_grounded_sources_replace_router_generated_sources(
        self,
        router_llm: Mock,
        load_prompt: Mock,
    ) -> None:
        from graph.nodes import synthesize_results

        router_llm.with_structured_output.return_value.invoke.return_value = {
            "parsed": FinalAnswerResult(
                title="Alegação verificada",
                answer="A informação é verdadeira.\n\nResposta.",
                sources=[SourceItem(
                    title="Fonte inventada pelo router",
                    url="https://example.com/inventada",
                )],
                classification="verdadeiro",
            ),
            "raw": AIMessage(content="", usage_metadata={
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
            }),
            "parsing_error": None,
        }

        result = synthesize_results({
            "query": "Alegação",
            "results": [{"source": "search_agent", "result": "Pesquisa"}],
            "sources": [
                SourceItem(title="Fonte Google", url="https://example.com/google"),
                SourceItem(title="Duplicada", url="https://example.com/google"),
            ],
        })

        self.assertEqual(
            result["final_answer"].sources,
            [SourceItem(title="Fonte Google", url="https://example.com/google")],
        )
        load_prompt.assert_called_once()

    @patch("graph.nodes.load_prompt", return_value="Sintetize {query}")
    @patch("graph.nodes.router_llm")
    def test_keeps_only_router_selected_grounded_sources(
        self,
        router_llm: Mock,
        _load_prompt: Mock,
    ) -> None:
        from graph.nodes import synthesize_results

        selected = SourceItem(
            title="Título produzido pelo router",
            url="https://example.com/selecionada",
        )
        router_llm.with_structured_output.return_value.invoke.return_value = {
            "parsed": FinalAnswerResult(
                title="Alegação verificada",
                answer="A informação é verdadeira.\n\nResposta.",
                sources=[
                    selected,
                    SourceItem(
                        title="Fonte inventada",
                        url="https://example.com/inventada",
                    ),
                ],
                classification="verdadeiro",
            ),
            "raw": AIMessage(content="", usage_metadata={
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
            }),
            "parsing_error": None,
        }

        result = synthesize_results({
            "query": "Alegação",
            "results": [{"source": "search_agent", "result": "Pesquisa"}],
            "sources": [
                SourceItem(
                    title="Fonte não selecionada",
                    url="https://example.com/outra",
                ),
                SourceItem(
                    title="Título fornecido pelo grounding",
                    url="https://example.com/selecionada",
                ),
            ],
        })

        self.assertEqual(result["final_answer"].sources, [SourceItem(
            title="Título fornecido pelo grounding",
            url="https://example.com/selecionada",
        )])

    def test_source_selection_is_limited_and_rejects_unknown_urls(self) -> None:
        from utils.sources import select_allowed_sources

        allowed = [
            SourceItem(
                title=f"Fonte {index}",
                url=f"https://example.com/{index}",
            )
            for index in range(12)
        ]
        requested = [
            SourceItem(title="Título do router", url=source.url)
            for source in allowed
        ] + [SourceItem(
            title="Inventada",
            url="https://example.com/inventada",
        )]

        selected = select_allowed_sources(requested, allowed)

        self.assertEqual(len(selected), 10)
        self.assertEqual(selected, allowed[:10])

    @patch("graph.nodes.load_prompt", return_value="Sintetize {query}")
    @patch("graph.nodes.router_llm")
    @patch("agents.search_agent.agent.search_agent")
    @patch("agents.search_agent.agent.SEARCH_GOOGLE_SEARCH_ENABLED", False)
    @patch("agents.transcription_agent.transcription_agent")
    @patch(
        "agents.image_authenticity_agent.load_prompt",
        return_value="Prompt de autenticidade",
    )
    @patch("agents.image_authenticity_agent.image_llm")
    @patch("agents.image_agent.load_prompt", return_value="Prompt visual")
    @patch("agents.image_agent.image_llm")
    def test_processes_multiple_media_before_one_search(
        self,
        image_llm: Mock,
        image_load_prompt: Mock,
        authenticity_llm: Mock,
        authenticity_load_prompt: Mock,
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
        authenticity_llm.with_structured_output.return_value.invoke.return_value = {
            "parsed": ImageAuthenticityModelResult(
                assessment="likely_ai_generated",
                confidence=0.75,
                signals=["Iluminação visual inconsistente."],
                limitations=["Imagem recomprimida."],
            ),
            "raw": AIMessage(content="", usage_metadata={
                "input_tokens": 80,
                "output_tokens": 20,
                "total_tokens": 100,
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
        self.assertEqual(len(state["image_authenticity_analyses"]), 1)
        self.assertEqual(
            state["image_authenticity_analyses"][0].attachment_index,
            0,
        )
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
            "INCONCLUSIVO: Conteúdos enviados e resultados da pesquisa",
        )
        self.assertEqual(len(state["model_usage"]), 6)
        image_load_prompt.assert_called_once()
        authenticity_load_prompt.assert_called_once()
        router_load_prompt.assert_called_once()


if __name__ == "__main__":
    unittest.main()
