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
                        answer="Resposta final",
                        sources=[],
                    )
                }
            }
        ]

    @patch.dict(
        os.environ,
        {"QDRANT_ENABLED": "true", "APP_VERSION": "test-version"},
    )
    @patch("jobs.get_qdrant_queue")
    @patch("jobs.get_final_results_queue")
    @patch("jobs.get_current_job")
    @patch("jobs.workflow.stream")
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

        with patch("jobs.perf_counter", side_effect=[100.0, 100.123]):
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
                {"answer": "Resposta final", "sources": []},
                "task-id",
            ),
        )

    @patch.dict(os.environ, {"QDRANT_ENABLED": "false"})
    @patch("jobs.get_qdrant_queue")
    @patch("jobs.get_final_results_queue")
    @patch("jobs.get_current_job")
    @patch("jobs.workflow.stream")
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
    @patch("jobs.logger")
    @patch("jobs.get_qdrant_queue")
    @patch("jobs.get_final_results_queue")
    @patch("jobs.get_current_job")
    @patch("jobs.workflow.stream")
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


if __name__ == "__main__":
    unittest.main()
