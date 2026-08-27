import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage

from graph.nodes import prepare_human_response, route_to_agents
from graph.state import ClassificationResult
from similarity.schemas import DuplicateCheckResult


class HumanResponseRoutingTest(unittest.TestCase):
    def test_routes_empty_classification_to_human_response(self) -> None:
        route = route_to_agents({"classifications": []})

        self.assertEqual(route, "human_response")

    def test_builds_pending_unclassified_answer(self) -> None:
        result = prepare_human_response({})

        self.assertTrue(result["human_response_required"])
        self.assertIsNone(result["final_answer"].classification)
        self.assertFalse(result["final_answer"].is_classified)
        self.assertEqual(result["final_answer"].sources, [])

    @patch("graph.nodes.router_llm")
    def test_greeting_finishes_workflow_without_search(
        self,
        router_llm: Mock,
    ) -> None:
        from graph.workflow import workflow

        router_llm.with_structured_output.return_value.invoke.return_value = {
            "parsed": ClassificationResult(classifications=[]),
            "parsing_error": None,
            "raw": AIMessage(content=""),
        }

        state = workflow.invoke({
            "query": "bom dia tudo bem?",
            "attachments": [],
        })

        self.assertTrue(state["human_response_required"])
        self.assertIsNone(state["final_answer"].classification)
        self.assertEqual(state["results"], [])

    @patch("jobs.analyze.wait_for_all_tracers")
    @patch("jobs.analyze.get_current_job")
    @patch("jobs.analyze.dispatch_completed_result")
    @patch("jobs.analyze.workflow.stream")
    @patch("jobs.analyze.run_duplicate_check")
    def test_human_response_reaches_panel_without_qdrant_persistence(
        self,
        run_duplicate_check: Mock,
        stream: Mock,
        dispatch_completed_result: Mock,
        get_current_job: Mock,
        _wait_for_all_tracers: Mock,
    ) -> None:
        from jobs import process_analyze_job

        pending = prepare_human_response({})
        run_duplicate_check.return_value = DuplicateCheckResult(outcome="skipped")
        stream.return_value = [{"human_response": pending}]
        get_current_job.return_value = SimpleNamespace(id="task-id")

        result = process_analyze_job(
            "bom dia tudo bem?",
            requester={"external_id": "+5568999999999"},
        )

        self.assertEqual(result["status"], "done")
        self.assertIsNone(result["final_answer"]["classification"])
        dispatch_completed_result.assert_called_once()
        call = dispatch_completed_result.call_args.kwargs
        self.assertFalse(call["persist_to_qdrant"])
        self.assertEqual(
            call["completed_result"]["result"]["query"],
            "bom dia tudo bem?",
        )
        self.assertEqual(
            call["completed_result"]["result"]["requester"],
            {"external_id": "+5568999999999"},
        )


class FailedAnalysisDeliveryTest(unittest.TestCase):
    def _job(self, *, should_retry: bool = False) -> SimpleNamespace:
        return SimpleNamespace(
            id="c824bf11-2a72-43dd-919b-a3f76de5fe04",
            args=(
                "Mensagem original",
                [],
                {"external_id": "+5568999999999"},
            ),
            should_retry=should_retry,
        )

    @patch("jobs.failed_analysis_delivery.enqueue_panel_result")
    def test_does_not_deliver_before_retry_is_exhausted(
        self,
        enqueue_panel_result: Mock,
    ) -> None:
        from jobs.failed_analysis_delivery import deliver_failed_analysis

        deliver_failed_analysis(
            self._job(should_retry=True),
            None,
            RuntimeError,
            RuntimeError("falha temporária"),
            None,
        )

        enqueue_panel_result.assert_not_called()

    @patch("jobs.failed_analysis_delivery.enqueue_panel_result")
    def test_delivers_terminal_failure_as_pending_human_item(
        self,
        enqueue_panel_result: Mock,
    ) -> None:
        from jobs.failed_analysis_delivery import deliver_failed_analysis

        deliver_failed_analysis(
            self._job(),
            None,
            RuntimeError,
            RuntimeError("pesquisa incompleta"),
            None,
        )

        enqueue_panel_result.assert_called_once()
        payload = enqueue_panel_result.call_args.kwargs["completed_result"]
        self.assertEqual(payload["status"], "done")
        self.assertEqual(payload["result"]["query"], "Mensagem original")
        self.assertEqual(
            payload["result"]["requester"],
            {"external_id": "+5568999999999"},
        )
        self.assertIsNone(
            payload["result"]["final_answer"]["classification"]
        )
        self.assertEqual(payload["error"], "pesquisa incompleta")


if __name__ == "__main__":
    unittest.main()
