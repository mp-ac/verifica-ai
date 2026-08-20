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
    @patch("jobs.analyze.get_current_job")
    @patch("jobs.analyze.wait_for_all_tracers")
    @patch("jobs.analyze.workflow.stream")
    def test_process_job_enqueues_qdrant_and_returns_done(
        self,
        stream: Mock,
        wait_for_tracers: Mock,
        get_analysis_job: Mock,
        get_current_job: Mock,
        get_final_results_queue: Mock,
        get_qdrant_queue: Mock,
    ) -> None:
        from jobs import process_analyze_job

        stream.return_value = self._workflow_updates()
        get_analysis_job.return_value = SimpleNamespace(id="task-id")
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
        trace_config = stream.call_args.kwargs["config"]
        self.assertEqual(trace_config["run_name"], "analyze_workflow")
        self.assertEqual(trace_config["tags"], ["flow:analyze"])
        self.assertEqual(trace_config["metadata"], {
            "task_id": "task-id",
            "app_version": "test-version",
            "retry_attempt": 0,
            "is_retry": False,
        })
        wait_for_tracers.assert_called_once_with()
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
                    "classification": None,
                    "is_classified": False,
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
                            "classification": None,
                            "is_classified": False,
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

    @patch(
        "jobs.analyze.wait_for_all_tracers",
        side_effect=RuntimeError("LangSmith unavailable"),
    )
    @patch("jobs.analyze.get_current_job")
    @patch("jobs.analyze.workflow.stream")
    def test_trace_flush_failure_does_not_fail_completed_analysis(
        self,
        stream: Mock,
        get_current_job: Mock,
        _wait_for_tracers: Mock,
    ) -> None:
        from jobs import process_analyze_job

        stream.return_value = self._workflow_updates()
        get_current_job.return_value = SimpleNamespace(id="task-id")

        with (
            patch("jobs.analyze.dispatch_completed_result"),
            self.assertLogs("jobs.analyze", level="ERROR"),
        ):
            result = process_analyze_job("Consulta")

        self.assertEqual(result["status"], "done")

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

    @patch.dict(
        os.environ,
        {"QDRANT_ENABLED": "true", "APP_VERSION": "test-version"},
    )
    @patch("qdrant.get_current_job")
    @patch("qdrant.wait_for_all_tracers")
    @patch("qdrant.trace")
    @patch("qdrant.save_final_answer")
    def test_qdrant_job_validates_payload_and_preserves_point_id(
        self,
        save_final_answer: Mock,
        trace: Mock,
        wait_for_tracers: Mock,
        get_current_job: Mock,
    ) -> None:
        from qdrant import COLLECTION_NAME, store_qdrant_result_job

        save_final_answer.return_value = "task-id"
        trace_run = trace.return_value.__enter__.return_value
        get_current_job.return_value = SimpleNamespace(
            id="qdrant-job-id",
            retries_left=2,
        )

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
        trace.assert_called_once_with(
            "verificaai_qdrant_store",
            inputs={"task_id": "task-id"},
            tags=["flow:qdrant_store"],
            metadata={
                "task_id": "task-id",
                "app_version": "test-version",
                "rq_job_id": "qdrant-job-id",
                "rq_retries_left": 2,
                "collection": COLLECTION_NAME,
            },
            parent="ignore",
            start_time=trace.call_args.kwargs["start_time"],
        )
        trace_run.end.assert_called_once_with(
            outputs={"stored": True, "point_id": "task-id"},
            error=None,
        )
        wait_for_tracers.assert_called_once_with()

        traced_data = {
            **trace.call_args.kwargs["inputs"],
            **trace.call_args.kwargs["metadata"],
            **trace_run.end.call_args.kwargs["outputs"],
        }
        self.assertNotIn("Consulta", str(traced_data))
        self.assertNotIn("Resposta final", str(traced_data))

    @patch.dict(os.environ, {"QDRANT_ENABLED": "true"})
    @patch("qdrant.get_current_job")
    @patch("qdrant.wait_for_all_tracers")
    @patch("qdrant.trace")
    @patch("qdrant.save_final_answer", side_effect=RuntimeError("Qdrant offline"))
    def test_qdrant_job_propagates_failure_for_rq_retry(
        self,
        save_final_answer: Mock,
        trace: Mock,
        wait_for_tracers: Mock,
        get_current_job: Mock,
    ) -> None:
        from qdrant import store_qdrant_result_job

        trace_run = trace.return_value.__enter__.return_value
        get_current_job.return_value = SimpleNamespace(
            id="qdrant-job-id",
            retries_left=1,
        )

        with self.assertRaisesRegex(RuntimeError, "Qdrant offline"):
            store_qdrant_result_job(
                query="Consulta",
                final_answer={"answer": "Resposta final", "sources": []},
                point_id="task-id",
            )

        trace_run.end.assert_called_once_with(
            outputs={"stored": False},
            error="RuntimeError",
        )
        wait_for_tracers.assert_called_once_with()

    @patch.dict(os.environ, {"QDRANT_ENABLED": "true"})
    @patch("qdrant.logger")
    @patch("qdrant.get_current_job")
    @patch("qdrant.wait_for_all_tracers")
    @patch("qdrant.trace", side_effect=RuntimeError("LangSmith indisponivel"))
    @patch("qdrant.save_final_answer", return_value="task-id")
    def test_trace_failure_does_not_fail_qdrant_store(
        self,
        _save_final_answer: Mock,
        _trace: Mock,
        _wait_for_tracers: Mock,
        get_current_job: Mock,
        logger: Mock,
    ) -> None:
        from qdrant import store_qdrant_result_job

        get_current_job.return_value = SimpleNamespace(id="qdrant-job-id")

        result = store_qdrant_result_job(
            query="Consulta",
            final_answer={"answer": "Resposta final", "sources": []},
            point_id="task-id",
        )

        self.assertEqual(result, "task-id")
        logger.exception.assert_called_once_with(
            "Falha ao registrar trace de persistencia no Qdrant."
        )

    @patch.dict(os.environ, {"QDRANT_ENABLED": "true"})
    @patch("qdrant.logger")
    @patch("qdrant.get_current_job")
    @patch(
        "qdrant.wait_for_all_tracers",
        side_effect=RuntimeError("LangSmith indisponivel"),
    )
    @patch("qdrant.trace")
    @patch("qdrant.save_final_answer", return_value="task-id")
    def test_trace_flush_failure_does_not_fail_qdrant_store(
        self,
        _save_final_answer: Mock,
        _trace: Mock,
        _wait_for_tracers: Mock,
        get_current_job: Mock,
        logger: Mock,
    ) -> None:
        from qdrant import store_qdrant_result_job

        get_current_job.return_value = SimpleNamespace(id="qdrant-job-id")

        result = store_qdrant_result_job(
            query="Consulta",
            final_answer={"answer": "Resposta final", "sources": []},
            point_id="task-id",
        )

        self.assertEqual(result, "task-id")
        logger.exception.assert_called_once_with(
            "Falha ao finalizar trace de persistencia no Qdrant."
        )

    @patch.dict(
        os.environ,
        {
            "FINAL_RESULTS_API_URL": "https://example.test/final-results",
            "FINAL_RESULTS_API_TOKEN": "secret-token",
            "FINAL_RESULTS_API_TIMEOUT_SECONDS": "15",
            "APP_VERSION": "test-version",
        },
    )
    @patch("final_results.get_current_job")
    @patch("final_results.wait_for_all_tracers")
    @patch("final_results.trace")
    @patch("final_results.requests.post")
    def test_final_result_job_sends_complete_result(
        self,
        post: Mock,
        trace: Mock,
        wait_for_tracers: Mock,
        get_current_job: Mock,
    ) -> None:
        from final_results import store_final_result_job

        response = post.return_value
        response.ok = True
        response.status_code = 201
        trace_run = trace.return_value.__enter__.return_value
        get_current_job.return_value = SimpleNamespace(
            id="delivery-job-id",
            retries_left=4,
        )
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
        trace.assert_called_once_with(
            "verificaai_painel_delivery",
            inputs={"task_id": "task-id"},
            tags=["flow:panel_delivery"],
            metadata={
                "task_id": "task-id",
                "app_version": "test-version",
                "rq_job_id": "delivery-job-id",
                "rq_retries_left": 4,
            },
            parent="ignore",
            start_time=trace.call_args.kwargs["start_time"],
        )
        trace_run.end.assert_called_once_with(
            outputs={
                "acknowledged": True,
                "http_status": 201,
            },
            error=None,
        )
        wait_for_tracers.assert_called_once_with()

        traced_data = {
            **trace.call_args.kwargs["inputs"],
            **trace.call_args.kwargs["metadata"],
            **trace_run.end.call_args.kwargs["outputs"],
        }
        self.assertNotIn("secret-token", str(traced_data))
        self.assertNotIn(final_result, traced_data.values())

    @patch.dict(
        os.environ,
        {
            "FINAL_RESULTS_API_URL": "https://example.test/final-results",
            "FINAL_RESULTS_API_TOKEN": "secret-token",
        },
    )
    @patch("final_results.get_current_job")
    @patch("final_results.wait_for_all_tracers")
    @patch("final_results.trace")
    @patch("final_results.requests.post")
    def test_final_result_job_traces_rejected_delivery_and_retries(
        self,
        post: Mock,
        trace: Mock,
        _wait_for_tracers: Mock,
        get_current_job: Mock,
    ) -> None:
        import requests

        from final_results import store_final_result_job

        response = post.return_value
        response.ok = False
        response.status_code = 503
        response.raise_for_status.side_effect = requests.HTTPError(
            "Painel indisponível"
        )
        trace_run = trace.return_value.__enter__.return_value
        get_current_job.return_value = SimpleNamespace(
            id="delivery-job-id",
            retries_left=3,
        )

        with self.assertRaisesRegex(requests.HTTPError, "Painel indisponível"):
            store_final_result_job("task-id", self._completed_result())

        trace_run.end.assert_called_once_with(
            outputs={
                "acknowledged": False,
                "http_status": 503,
            },
            error="HTTP 503",
        )

    @patch.dict(
        os.environ,
        {
            "FINAL_RESULTS_API_URL": "https://example.test/final-results",
            "FINAL_RESULTS_API_TOKEN": "secret-token",
        },
    )
    @patch("final_results.get_current_job")
    @patch("final_results.wait_for_all_tracers")
    @patch("final_results.trace")
    @patch("final_results.requests.post")
    def test_final_result_job_traces_safe_validation_error_fields(
        self,
        post: Mock,
        trace: Mock,
        _wait_for_tracers: Mock,
        get_current_job: Mock,
    ) -> None:
        import requests

        from final_results import store_final_result_job

        response = post.return_value
        response.ok = False
        response.status_code = 422
        response.json.return_value = {
            "message": "The given data was invalid.",
            "errors": {
                "result.final_answer.sources.0.url": [
                    "The rejected value was https://private.example/token."
                ],
                "unsafe field with spaces": ["Must not reach the trace."],
            },
        }
        response.raise_for_status.side_effect = requests.HTTPError(
            "422 Client Error"
        )
        trace_run = trace.return_value.__enter__.return_value
        get_current_job.return_value = SimpleNamespace(
            id="delivery-job-id",
            retries_left=3,
        )

        with self.assertRaisesRegex(requests.HTTPError, "422 Client Error"):
            store_final_result_job("task-id", self._completed_result())

        trace_run.end.assert_called_once_with(
            outputs={
                "acknowledged": False,
                "http_status": 422,
                "failure_type": "validation_error",
                "validation_error_fields": [
                    "result.final_answer.sources.0.url"
                ],
            },
            error="HTTP 422",
        )
        traced_data = str(trace_run.end.call_args.kwargs)
        self.assertNotIn("private.example", traced_data)
        self.assertNotIn("Must not reach the trace", traced_data)

    @patch.dict(
        os.environ,
        {
            "FINAL_RESULTS_API_URL": "https://example.test/final-results",
            "FINAL_RESULTS_API_TOKEN": "secret-token",
        },
    )
    @patch("final_results.get_current_job")
    @patch("final_results.wait_for_all_tracers")
    @patch("final_results.trace")
    @patch("final_results.requests.post")
    def test_final_result_job_traces_connection_failure_and_retries(
        self,
        post: Mock,
        trace: Mock,
        _wait_for_tracers: Mock,
        get_current_job: Mock,
    ) -> None:
        import requests

        from final_results import store_final_result_job

        post.side_effect = requests.ConnectionError("Painel indisponivel")
        trace_run = trace.return_value.__enter__.return_value
        get_current_job.return_value = SimpleNamespace(
            id="delivery-job-id",
            retries_left=3,
        )

        with self.assertRaises(requests.ConnectionError):
            store_final_result_job("task-id", self._completed_result())

        trace_run.end.assert_called_once_with(
            outputs={
                "acknowledged": False,
                "http_status": None,
            },
            error="ConnectionError",
        )

    @patch.dict(
        os.environ,
        {
            "FINAL_RESULTS_API_URL": "https://example.test/final-results",
            "FINAL_RESULTS_API_TOKEN": "secret-token",
        },
    )
    @patch("final_results.logger")
    @patch("final_results.get_current_job")
    @patch("final_results.wait_for_all_tracers")
    @patch(
        "final_results.trace",
        side_effect=RuntimeError("LangSmith indisponivel"),
    )
    @patch("final_results.requests.post")
    def test_trace_failure_does_not_fail_panel_delivery(
        self,
        post: Mock,
        _trace: Mock,
        _wait_for_tracers: Mock,
        get_current_job: Mock,
        logger: Mock,
    ) -> None:
        from final_results import store_final_result_job

        post.return_value.ok = True
        post.return_value.status_code = 201
        get_current_job.return_value = SimpleNamespace(id="delivery-job-id")

        store_final_result_job("task-id", self._completed_result())

        post.return_value.raise_for_status.assert_called_once_with()
        logger.exception.assert_called_once_with(
            "Falha ao registrar trace de entrega ao painel."
        )

    @patch.dict(
        os.environ,
        {
            "FINAL_RESULTS_API_URL": "https://example.test/final-results",
            "FINAL_RESULTS_API_TOKEN": "secret-token",
        },
    )
    @patch("final_results.logger")
    @patch("final_results.get_current_job")
    @patch(
        "final_results.wait_for_all_tracers",
        side_effect=RuntimeError("LangSmith indisponível"),
    )
    @patch("final_results.trace")
    @patch("final_results.requests.post")
    def test_trace_flush_failure_does_not_fail_panel_delivery(
        self,
        post: Mock,
        _trace: Mock,
        _wait_for_tracers: Mock,
        get_current_job: Mock,
        logger: Mock,
    ) -> None:
        from final_results import store_final_result_job

        post.return_value.ok = True
        post.return_value.status_code = 201
        get_current_job.return_value = SimpleNamespace(id="delivery-job-id")

        store_final_result_job("task-id", self._completed_result())

        logger.exception.assert_called_once_with(
            "Falha ao finalizar trace de entrega ao painel."
        )


if __name__ == "__main__":
    unittest.main()
