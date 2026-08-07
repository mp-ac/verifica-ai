import os
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from graph.state import FinalAnswerResult


class QdrantQueueTest(unittest.TestCase):
    def _workflow_updates(self) -> list[dict]:
        return [
            {
                "synthesize": {
                    "final_answer": FinalAnswerResult(
                        title="Título da resposta",
                        answer="Resposta final",
                        sources=[],
                    )
                }
            }
        ]

    def _completed_result(self) -> dict:
        return {
            "status": "done",
            "result": {
                "query": "Consulta",
                "final_answer": {
                    "title": "Título da resposta",
                    "answer": "Resposta final",
                    "sources": [],
                },
            },
            "execution": {
                "models": [],
                "agents": ["search_agent"],
                "tools": ["fetch_url"],
                "duration_ms": 123,
                "completed_at": "2026-08-04T10:00:00Z",
                "app_version": "test-version",
            },
            "error": None,
        }

    @patch.dict(
        os.environ,
        {"QDRANT_ENABLED": "true", "APP_VERSION": "test-version"},
    )
    @patch("jobs.result_dispatch.qdrant.get_qdrant_queue")
    @patch("jobs.result_dispatch.panel.get_final_results_queue")
    @patch("jobs.result_dispatch.dispatcher.get_current_job")
    @patch("jobs.analyze.workflow.stream")
    def test_process_job_enqueues_qdrant_and_returns_done(
        self,
        stream: Mock,
        get_current_job: Mock,
        get_final_results_queue: Mock,
        get_qdrant_queue: Mock,
    ) -> None:
        from jobs import process_analyze_job

        stream.return_value = self._workflow_updates()
        get_current_job.return_value = SimpleNamespace(id="task-id")

        with (
            patch("jobs.analyze.perf_counter", return_value=100.0),
            patch(
                "jobs.execution_metadata.perf_counter",
                return_value=100.123,
            ),
        ):
            result = process_analyze_job("Consulta")

        self.assertEqual(result["status"], "done")
        execution = result["execution"]
        self.assertEqual(execution["duration_ms"], 123)
        self.assertEqual(execution["app_version"], "test-version")
        completed_at = datetime.fromisoformat(execution["completed_at"])
        self.assertIsNotNone(completed_at.tzinfo)
        enqueue = get_qdrant_queue.return_value.enqueue_call
        enqueue.assert_called_once()
        self.assertEqual(
            enqueue.call_args.kwargs["func"],
            "qdrant.store_qdrant_result_job",
        )
        self.assertEqual(
            enqueue.call_args.kwargs["args"],
            (
                "Consulta",
                {
                    "title": "Título da resposta",
                    "answer": "Resposta final",
                    "sources": [],
                },
                "task-id",
            ),
        )
        final_results_enqueue = (
            get_final_results_queue.return_value.enqueue_call
        )
        final_results_enqueue.assert_called_once()
        self.assertEqual(
            final_results_enqueue.call_args.kwargs["args"],
            (
                "task-id",
                {
                    "status": "done",
                    "result": {
                        "query": "Consulta",
                        "attachments": [],
                        "final_answer": {
                            "title": "Título da resposta",
                            "answer": "Resposta final",
                            "sources": [],
                        },
                    },
                    "execution": execution,
                    "error": None,
                },
            ),
        )

    @patch.dict(os.environ, {"QDRANT_ENABLED": "true"})
    @patch("jobs.result_dispatch.qdrant.get_qdrant_queue")
    @patch("jobs.result_dispatch.panel.get_final_results_queue")
    @patch("jobs.result_dispatch.dispatcher.get_current_job")
    @patch("jobs.analyze.workflow.stream")
    def test_requester_is_delivered_to_panel_but_not_qdrant(
        self,
        stream: Mock,
        get_current_job: Mock,
        get_final_results_queue: Mock,
        get_qdrant_queue: Mock,
    ) -> None:
        from jobs import process_analyze_job

        stream.return_value = self._workflow_updates()
        get_current_job.return_value = SimpleNamespace(id="task-id")
        requester = {
            "application": {
                "id": "c824bf11-2a72-43dd-919b-a3f76de5fe04",
                "name": "Agente WhatsApp",
            },
            "external_id": "+5568999999999",
            "conversation_id": None,
            "message_id": None,
        }

        result = process_analyze_job("Consulta", requester=requester)

        self.assertNotIn("requester", result)
        delivery_args = (
            get_final_results_queue.return_value.enqueue_call.call_args.kwargs[
                "args"
            ]
        )
        delivery = delivery_args[1]
        self.assertEqual(delivery["result"]["requester"], requester)
        qdrant_args = (
            get_qdrant_queue.return_value.enqueue_call.call_args.kwargs["args"]
        )
        self.assertEqual(len(qdrant_args), 3)
        self.assertNotIn(requester, qdrant_args)

    @patch.dict(os.environ, {"QDRANT_ENABLED": "false"})
    @patch("jobs.result_dispatch.qdrant.get_qdrant_queue")
    @patch("jobs.result_dispatch.panel.get_final_results_queue")
    @patch("jobs.result_dispatch.dispatcher.get_current_job")
    @patch("jobs.analyze.workflow.stream")
    def test_process_job_skips_qdrant_when_disabled(
        self,
        stream: Mock,
        get_current_job: Mock,
        get_final_results_queue: Mock,
        get_qdrant_queue: Mock,
    ) -> None:
        from jobs import process_analyze_job

        stream.return_value = self._workflow_updates()
        get_current_job.return_value = SimpleNamespace(id="task-id")

        result = process_analyze_job("Consulta")

        self.assertEqual(result["status"], "done")
        get_qdrant_queue.assert_not_called()

    @patch.dict(os.environ, {"QDRANT_ENABLED": "true"})
    @patch("jobs.result_dispatch.qdrant.logger")
    @patch("jobs.result_dispatch.qdrant.get_qdrant_queue")
    @patch("jobs.result_dispatch.panel.get_final_results_queue")
    @patch("jobs.result_dispatch.dispatcher.get_current_job")
    @patch("jobs.analyze.workflow.stream")
    def test_process_job_returns_done_when_qdrant_enqueue_fails(
        self,
        stream: Mock,
        get_current_job: Mock,
        get_final_results_queue: Mock,
        get_qdrant_queue: Mock,
        logger: Mock,
    ) -> None:
        from jobs import process_analyze_job

        stream.return_value = self._workflow_updates()
        get_current_job.return_value = SimpleNamespace(id="task-id")
        get_qdrant_queue.return_value.enqueue_call.side_effect = RuntimeError

        result = process_analyze_job("Consulta")

        self.assertEqual(result["status"], "done")
        logger.warning.assert_called_once()

    @patch.dict(os.environ, {"QDRANT_ENABLED": "true"})
    @patch("qdrant.save_final_answer")
    def test_qdrant_job_validates_payload_and_preserves_point_id(
        self,
        save_final_answer: Mock,
    ) -> None:
        from qdrant import store_qdrant_result_job

        save_final_answer.return_value = "task-id"

        result = store_qdrant_result_job(
            query="Consulta",
            final_answer={"answer": "Resposta final", "sources": []},
            point_id="task-id",
        )

        self.assertEqual(result, "task-id")
        call = save_final_answer.call_args.kwargs
        self.assertEqual(call["query"], "Consulta")
        self.assertIsInstance(call["final_answer"], FinalAnswerResult)
        self.assertEqual(call["point_id"], "task-id")

    @patch.dict(os.environ, {"QDRANT_ENABLED": "true"})
    @patch("qdrant.save_final_answer", side_effect=RuntimeError("Qdrant offline"))
    def test_qdrant_job_propagates_failure_for_rq_retry(
        self,
        save_final_answer: Mock,
    ) -> None:
        from qdrant import store_qdrant_result_job

        with self.assertRaisesRegex(RuntimeError, "Qdrant offline"):
            store_qdrant_result_job(
                query="Consulta",
                final_answer={"answer": "Resposta final", "sources": []},
                point_id="task-id",
            )

    @patch.dict(
        os.environ,
        {
            "FINAL_RESULTS_API_URL": "https://example.test/final-results",
            "FINAL_RESULTS_API_TOKEN": "secret-token",
        },
    )
    @patch("final_results.requests.post")
    def test_final_result_job_sends_complete_result(
        self,
        post: Mock,
    ) -> None:
        from final_results import store_final_result_job

        response = post.return_value
        final_result = self._completed_result()

        store_final_result_job("task-id", final_result)

        post.assert_called_once_with(
            "https://example.test/final-results",
            json={"task_id": "task-id", **final_result},
            headers={
                "Authorization": "Bearer secret-token",
                "Accept": "application/json",
            },
            timeout=15,
        )
        response.raise_for_status.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
