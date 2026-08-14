import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID

from fastapi import HTTPException
from langchain_core.messages import AIMessage
from pydantic import ValidationError

from reanalysis.graph.nodes import (
    format_reanalysis_research_query,
    route_reanalysis,
)
from graph.state import Attachment, FinalAnswerResult
from reanalysis.schemas import PanelFinalResult, ReanalyzeRequest


FINAL_RESULT_ID = UUID("c824bf11-2a72-43dd-919b-a3f76de5fe04")
REANALYSIS_ID = UUID("66c97611-3931-4f96-b963-17f5121b2353")


def make_panel_final_result(**overrides) -> PanelFinalResult:
    data = {
        "id": FINAL_RESULT_ID,
        "query": "A publicação representa um fato verdadeiro?",
        "title": "Análise original",
        "attachments": [],
        "final_result": "A imagem foi produzida por inteligência artificial.",
        "classification": "falso",
        "sources": [{
            "title": "Fonte anterior",
            "url": "https://example.com/fonte-anterior",
        }],
        "is_classified": False,
    }
    data.update(overrides)
    return PanelFinalResult.model_validate(data)


class ReanalysisSchemaTest(unittest.TestCase):
    def test_normalizes_prompt(self) -> None:
        payload = ReanalyzeRequest(
            reanalysis_id=REANALYSIS_ID,
            final_result_id=FINAL_RESULT_ID,
            prompt="  Verifique também o conteúdo semântico.  ",
        )

        self.assertEqual(
            payload.prompt,
            "Verifique também o conteúdo semântico.",
        )

    def test_rejects_blank_prompt(self) -> None:
        with self.assertRaises(ValidationError):
            ReanalyzeRequest(
                reanalysis_id=REANALYSIS_ID,
                final_result_id=FINAL_RESULT_ID,
                prompt="   ",
            )

    def test_normalizes_nullable_panel_collections(self) -> None:
        final_result = make_panel_final_result(
            attachments=None,
            sources=None,
        )

        self.assertEqual(final_result.attachments, [])
        self.assertEqual(final_result.sources, [])


class PanelIntegrationTest(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "FINAL_RESULTS_API_URL": "https://panel.test/api/v1/final-results",
            "FINAL_RESULTS_API_TOKEN": "secret-token",
            "FINAL_RESULTS_API_TIMEOUT_SECONDS": "15",
        },
    )
    @patch("reanalysis.verificaai_painel.requests.get")
    def test_fetches_original_final_result(self, get: Mock) -> None:
        from reanalysis.verificaai_painel import fetch_final_result

        response = get.return_value
        response.status_code = 200
        response.json.return_value = {
            "data": make_panel_final_result().model_dump(
                mode="json",
                by_alias=True,
            )
        }

        result = fetch_final_result(FINAL_RESULT_ID)

        self.assertEqual(result.id, FINAL_RESULT_ID)
        get.assert_called_once_with(
            f"https://panel.test/api/v1/final-results/{FINAL_RESULT_ID}",
            headers={
                "Authorization": "Bearer secret-token",
                "Accept": "application/json",
            },
            timeout=15,
        )
        response.raise_for_status.assert_called_once_with()

    @patch.dict(
        os.environ,
        {
            "FINAL_RESULTS_API_URL": "https://panel.test/api/v1/final-results",
            "FINAL_RESULTS_API_TOKEN": "secret-token",
            "FINAL_RESULTS_API_TIMEOUT_SECONDS": "15",
        },
    )
    @patch("reanalysis.verificaai_painel.requests.get")
    def test_rejects_result_with_human_classification(self, get: Mock) -> None:
        from reanalysis.verificaai_painel import (
            FinalResultAlreadyReviewedError,
            fetch_final_result,
        )

        response = get.return_value
        response.status_code = 200
        response.json.return_value = {
            "data": make_panel_final_result(
                is_classified=True,
            ).model_dump(mode="json", by_alias=True)
        }

        with self.assertRaises(FinalResultAlreadyReviewedError):
            fetch_final_result(FINAL_RESULT_ID)

    @patch.dict(
        os.environ,
        {
            "REANALYSIS_RESULTS_API_URL": (
                "https://panel.test/api/v1/final-result-reanalyses"
            ),
            "FINAL_RESULTS_API_TOKEN": "secret-token",
            "FINAL_RESULTS_API_TIMEOUT_SECONDS": "15",
        },
    )
    @patch("reanalysis.verificaai_painel.requests.put")
    def test_stores_reanalysis_result(self, put: Mock) -> None:
        from reanalysis.verificaai_painel import store_reanalysis_result_job

        completed_result = {
            "status": "done",
            "result": {"reanalysis_id": str(REANALYSIS_ID)},
            "execution": {"duration_ms": 123},
            "error": None,
        }

        store_reanalysis_result_job(
            str(REANALYSIS_ID),
            "reanalysis-task-id",
            completed_result,
        )

        put.assert_called_once_with(
            (
                "https://panel.test/api/v1/final-result-reanalyses/"
                f"{REANALYSIS_ID}/result"
            ),
            json={
                **completed_result,
                "task_id": "reanalysis-task-id",
            },
            headers={
                "Authorization": "Bearer secret-token",
                "Accept": "application/json",
            },
            timeout=15,
        )
        put.return_value.raise_for_status.assert_called_once_with()


class ReanalysisResultDeliveryTest(unittest.TestCase):
    @patch.dict(
        os.environ,
        {"FINAL_RESULTS_RETRY_INTERVALS_SECONDS": "10,30,60,300,900"},
    )
    @patch("reanalysis.result_delivery.get_final_results_queue")
    def test_enqueues_completed_result_for_panel_delivery(
        self,
        get_queue: Mock,
    ) -> None:
        from reanalysis.result_delivery import deliver_completed_reanalysis
        from reanalysis.verificaai_painel import store_reanalysis_result_job

        completed_result = {
            "status": "done",
            "result": {"reanalysis_id": str(REANALYSIS_ID)},
            "execution": {},
            "error": None,
        }
        job = SimpleNamespace(
            id="reanalysis-task-id",
            args=(str(REANALYSIS_ID), {}, "Amplie a pesquisa."),
        )

        deliver_completed_reanalysis(job, Mock(), completed_result)

        enqueue_call = get_queue.return_value.enqueue_call.call_args.kwargs
        self.assertIs(enqueue_call["func"], store_reanalysis_result_job)
        self.assertEqual(
            enqueue_call["args"],
            (
                str(REANALYSIS_ID),
                "reanalysis-task-id",
                completed_result,
            ),
        )
        self.assertEqual(enqueue_call["retry"].intervals, [10, 30, 60, 300, 900])

    @patch("reanalysis.result_delivery.enqueue_reanalysis_result")
    def test_enqueues_failed_result_for_panel_delivery(
        self,
        enqueue_result: Mock,
    ) -> None:
        from reanalysis.result_delivery import deliver_failed_reanalysis

        job = SimpleNamespace(
            id="reanalysis-task-id",
            args=(str(REANALYSIS_ID), {}, "Amplie a pesquisa."),
        )

        deliver_failed_reanalysis(
            job,
            Mock(),
            RuntimeError,
            RuntimeError("Falha no workflow."),
            None,
        )

        payload = enqueue_result.call_args.kwargs
        self.assertEqual(payload["reanalysis_id"], str(REANALYSIS_ID))
        self.assertEqual(payload["task_id"], "reanalysis-task-id")
        self.assertEqual(payload["completed_result"]["status"], "failed")
        self.assertEqual(
            payload["completed_result"]["error"],
            "Falha no workflow.",
        )


class ReanalysisRoutingTest(unittest.TestCase):
    def _state(self, attachments=None) -> dict:
        return {
            "query": "Consulta original",
            "prompt": "Pesquise o conteúdo representado na imagem.",
            "attachments": attachments or [],
            "original_final_answer": make_panel_final_result().to_final_answer(),
            "media_contexts": [],
            "results": [],
        }

    def test_research_query_contains_previous_answer_and_human_prompt(self) -> None:
        query = format_reanalysis_research_query(self._state())

        self.assertIn("<resultado_anterior>", query)
        self.assertIn(
            "A imagem foi produzida por inteligência artificial.",
            query,
        )
        self.assertIn("<instrucao_do_analista>", query)
        self.assertIn("Pesquise o conteúdo representado", query)
        self.assertIn("https://example.com/fonte-anterior", query)

    def test_routes_original_image_through_image_agent(self) -> None:
        sends = route_reanalysis(self._state([
            Attachment(
                type="image",
                url="https://example.com/imagem.jpg",
            )
        ]))

        self.assertEqual(len(sends), 1)
        self.assertEqual(sends[0].node, "image_agent")


class ReanalysisApiTest(unittest.IsolatedAsyncioTestCase):
    @patch("reanalysis.api.q")
    @patch("reanalysis.api.fetch_final_result")
    async def test_fetches_context_before_enqueue(
        self,
        fetch_final_result: Mock,
        queue: Mock,
    ) -> None:
        from reanalysis.api import reanalyze

        final_result = make_panel_final_result()
        fetch_final_result.return_value = final_result
        queue.enqueue.return_value = SimpleNamespace(id="reanalysis-task-id")
        payload = ReanalyzeRequest(
            reanalysis_id=REANALYSIS_ID,
            final_result_id=FINAL_RESULT_ID,
            prompt="Amplie a pesquisa.",
        )

        response = await reanalyze(payload, SimpleNamespace())

        self.assertEqual(response.task_id, "reanalysis-task-id")
        fetch_final_result.assert_called_once_with(FINAL_RESULT_ID)
        enqueue_args = queue.enqueue.call_args.args
        self.assertEqual(enqueue_args[1], str(REANALYSIS_ID))
        self.assertEqual(enqueue_args[2]["id"], str(FINAL_RESULT_ID))
        self.assertEqual(enqueue_args[3], "Amplie a pesquisa.")
        enqueue_options = queue.enqueue.call_args.kwargs
        self.assertEqual(
            enqueue_options["on_success"].__name__,
            "deliver_completed_reanalysis",
        )
        self.assertEqual(
            enqueue_options["on_failure"].__name__,
            "deliver_failed_reanalysis",
        )
        self.assertEqual(
            enqueue_options["on_stopped"].__name__,
            "deliver_stopped_reanalysis",
        )

    @patch("reanalysis.api.fetch_final_result")
    async def test_returns_conflict_for_human_review(
        self,
        fetch_final_result: Mock,
    ) -> None:
        from reanalysis.api import reanalyze
        from reanalysis.verificaai_painel import (
            FinalResultAlreadyReviewedError,
        )

        fetch_final_result.side_effect = FinalResultAlreadyReviewedError(
            "Resultado já revisado."
        )
        payload = ReanalyzeRequest(
            reanalysis_id=REANALYSIS_ID,
            final_result_id=FINAL_RESULT_ID,
            prompt="Amplie a pesquisa.",
        )

        with self.assertRaises(HTTPException) as context:
            await reanalyze(payload, SimpleNamespace())

        self.assertEqual(context.exception.status_code, 409)

    @patch("reanalysis.api.Job.fetch")
    async def test_returns_completed_reanalysis_status(
        self,
        fetch_job: Mock,
    ) -> None:
        from reanalysis.api import get_reanalysis_status

        fetch_job.return_value = SimpleNamespace(
            is_queued=False,
            is_started=False,
            is_finished=True,
            is_failed=False,
            result={
                "status": "done",
                "result": {
                    "reanalysis_id": str(REANALYSIS_ID),
                    "final_result_id": str(FINAL_RESULT_ID),
                    "prompt": "Amplie a pesquisa.",
                    "final_answer": {
                        "title": "Análise ampliada",
                        "answer": "A informação é enganosa.\n\nResposta ampliada.",
                        "classification": "enganoso",
                        "sources": [],
                    },
                },
                "execution": {
                    "models": [],
                    "agents": ["search_agent"],
                    "tools": ["get_links", "fetch_url"],
                    "duration_ms": 123,
                    "completed_at": "2026-08-11T12:00:00Z",
                    "app_version": "test-version",
                },
                "error": None,
            },
        )

        response = await get_reanalysis_status(
            "reanalysis-task-id",
            SimpleNamespace(),
        )

        self.assertEqual(response.status, "done")
        self.assertEqual(response.result.reanalysis_id, REANALYSIS_ID)
        self.assertEqual(response.result.final_result_id, FINAL_RESULT_ID)
        self.assertEqual(
            response.result.final_answer.classification,
            "enganoso",
        )
        self.assertEqual(response.execution.agents, ["search_agent"])


class ReanalysisJobTest(unittest.TestCase):
    @patch.dict(os.environ, {"APP_VERSION": "test-version"})
    @patch("reanalysis.job.wait_for_all_tracers")
    @patch("reanalysis.job.get_current_job")
    @patch("reanalysis.job.reanalysis_workflow.stream")
    def test_returns_cumulative_result_with_execution_metadata(
        self,
        stream: Mock,
        get_current_job: Mock,
        wait_for_tracers: Mock,
    ) -> None:
        from reanalysis.job import process_reanalyze_job

        get_current_job.return_value = SimpleNamespace(id="reanalysis-task-id")
        stream.return_value = [
            {
                "search_agent": {
                    "tools": ["get_links", "fetch_url"],
                    "model_usage": [{
                        "role": "search",
                        "input_tokens": 100,
                        "output_tokens": 20,
                        "thinking_tokens": 0,
                        "cached_input_tokens": 0,
                        "total_tokens": 120,
                    }],
                }
            },
            {
                "synthesize": {
                    "final_answer": FinalAnswerResult(
                        title="Análise ampliada",
                        answer="A informação é enganosa.\n\nResposta ampliada.",
                        classification="enganoso",
                        sources=[],
                    ),
                    "model_usage": [{
                        "role": "router",
                        "input_tokens": 80,
                        "output_tokens": 20,
                        "thinking_tokens": 0,
                        "cached_input_tokens": 0,
                        "total_tokens": 100,
                    }],
                }
            },
        ]

        result = process_reanalyze_job(
            str(REANALYSIS_ID),
            make_panel_final_result().model_dump(mode="json"),
            "Amplie a pesquisa.",
        )

        self.assertEqual(result["status"], "done")
        self.assertEqual(
            result["result"]["reanalysis_id"],
            str(REANALYSIS_ID),
        )
        self.assertEqual(
            result["result"]["final_result_id"],
            str(FINAL_RESULT_ID),
        )
        self.assertEqual(
            result["result"]["final_answer"]["classification"],
            "enganoso",
        )
        self.assertEqual(
            result["execution"]["agents"],
            ["search_agent"],
        )
        self.assertEqual(
            result["execution"]["tools"],
            ["fetch_url", "get_links"],
        )
        trace_config = stream.call_args.kwargs["config"]
        self.assertEqual(trace_config["run_name"], "reanalysis_workflow")
        self.assertEqual(trace_config["tags"], ["flow:reanalysis"])
        self.assertEqual(trace_config["metadata"], {
            "task_id": "reanalysis-task-id",
            "reanalysis_id": str(REANALYSIS_ID),
            "app_version": "test-version",
        })
        wait_for_tracers.assert_called_once_with()

    @patch(
        "reanalysis.job.wait_for_all_tracers",
        side_effect=RuntimeError("LangSmith indisponível"),
    )
    @patch("reanalysis.job.get_current_job")
    @patch("reanalysis.job.reanalysis_workflow.stream")
    def test_trace_flush_failure_does_not_fail_completed_reanalysis(
        self,
        stream: Mock,
        get_current_job: Mock,
        _wait_for_tracers: Mock,
    ) -> None:
        from reanalysis.job import process_reanalyze_job

        get_current_job.return_value = SimpleNamespace(id="reanalysis-task-id")
        stream.return_value = [{
            "synthesize": {
                "final_answer": FinalAnswerResult(
                    title="Análise ampliada",
                    answer="Resposta ampliada.",
                    classification="inconclusivo",
                    sources=[],
                ),
            }
        }]

        with self.assertLogs("reanalysis.job", level="ERROR"):
            result = process_reanalyze_job(
                str(REANALYSIS_ID),
                make_panel_final_result().model_dump(mode="json"),
                "Amplie a pesquisa.",
            )

        self.assertEqual(result["status"], "done")


class ReanalysisSynthesisTest(unittest.TestCase):
    @patch(
        "reanalysis.graph.nodes.load_prompt",
        return_value="Produza uma resposta cumulativa.",
    )
    @patch("reanalysis.graph.nodes.router_llm")
    def test_synthesis_receives_previous_answer_and_new_research(
        self,
        router_llm: Mock,
        load_prompt: Mock,
    ) -> None:
        from reanalysis.graph.nodes import synthesize_reanalysis

        structured_llm = router_llm.with_structured_output.return_value
        structured_llm.invoke.return_value = {
            "parsed": FinalAnswerResult(
                title="Análise ampliada",
                answer="A informação é enganosa.\n\nResposta anterior ampliada.",
                classification="enganoso",
                sources=[],
            ),
            "raw": AIMessage(content="", usage_metadata={
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            }),
            "parsing_error": None,
        }
        state = {
            "query": "Consulta original",
            "prompt": "Analise também o conteúdo semântico.",
            "attachments": [],
            "original_final_answer": make_panel_final_result().to_final_answer(),
            "results": [{
                "source": "search_agent",
                "result": "A nova pesquisa encontrou contexto adicional.",
            }],
        }

        result = synthesize_reanalysis(state)

        messages = structured_llm.invoke.call_args.args[0]
        self.assertIn(
            "A imagem foi produzida por inteligência artificial.",
            messages[1]["content"],
        )
        self.assertIn(
            "Analise também o conteúdo semântico.",
            messages[1]["content"],
        )
        self.assertIn("contexto adicional", messages[1]["content"])
        self.assertNotIn(
            "A imagem foi produzida por inteligência artificial.",
            messages[0]["content"],
        )
        self.assertEqual(result["final_answer"].classification, "enganoso")
        self.assertEqual(
            result["final_answer"].title,
            "ENGANOSO: Análise ampliada",
        )
        load_prompt.assert_called_once()


class ReanalysisWorkflowTest(unittest.TestCase):
    @patch(
        "reanalysis.graph.nodes.load_prompt",
        return_value="Produza uma resposta cumulativa.",
    )
    @patch("reanalysis.graph.nodes.router_llm")
    @patch("agents.search_agent.search_agent")
    @patch("agents.image_agent.load_prompt", return_value="Prompt visual")
    @patch("agents.image_agent.image_llm")
    def test_reprocesses_image_before_search_and_cumulative_synthesis(
        self,
        image_llm: Mock,
        image_load_prompt: Mock,
        search_agent: Mock,
        router_llm: Mock,
        synthesis_load_prompt: Mock,
    ) -> None:
        from reanalysis.graph.workflow import reanalysis_workflow
        from graph.state import ImageAnalysisResult

        image_llm.with_structured_output.return_value.invoke.return_value = {
            "parsed": ImageAnalysisResult(
                visible_text="Texto da publicação",
                visual_context="Imagem sintética sobre um fato público.",
                claims=["A publicação representa um acontecimento real."],
                research_query="acontecimento representado evidências",
            ),
            "raw": AIMessage(content="", usage_metadata={
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
            }),
            "parsing_error": None,
        }
        search_agent.invoke.return_value = {
            "messages": [AIMessage(content="A pesquisa verificou o fato representado.")]
        }
        router_llm.with_structured_output.return_value.invoke.return_value = {
            "parsed": FinalAnswerResult(
                title="Imagem sintética e conteúdo representado",
                answer="A informação é enganosa.\n\nResposta cumulativa.",
                classification="enganoso",
                sources=[],
            ),
            "raw": AIMessage(content="", usage_metadata={
                "input_tokens": 200,
                "output_tokens": 40,
                "total_tokens": 240,
            }),
            "parsing_error": None,
        }

        state = reanalysis_workflow.invoke({
            "query": "Consulta original",
            "prompt": "Verifique também o conteúdo representado.",
            "attachments": [Attachment(
                type="image",
                url="https://example.com/imagem.jpg",
            )],
            "original_final_answer": make_panel_final_result().to_final_answer(),
        })

        image_llm.with_structured_output.assert_called_once()
        search_agent.invoke.assert_called_once()
        research_query = (
            search_agent.invoke.call_args.args[0]["messages"][0]["content"]
        )
        self.assertIn("Imagem sintética sobre um fato público", research_query)
        self.assertIn(
            "A imagem foi produzida por inteligência artificial.",
            research_query,
        )
        self.assertEqual(state["final_answer"].classification, "enganoso")
        image_load_prompt.assert_called_once()
        synthesis_load_prompt.assert_called_once()


if __name__ == "__main__":
    unittest.main()
