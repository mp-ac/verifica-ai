import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID

from queueing import retry_intervals
from schemas.api import AnalyzeRequest


class AnalyzeRetryConfigTest(unittest.TestCase):
    def test_reads_retry_intervals_from_environment(self) -> None:
        with patch.dict(
            os.environ,
            {"RQ_RETRY_INTERVALS_SECONDS": "30, 60,120, 300,600"},
        ):
            self.assertEqual(retry_intervals(), [30, 60, 120, 300, 600])

    def test_empty_retry_intervals_disable_retries(self) -> None:
        with patch.dict(
            os.environ,
            {"RQ_RETRY_INTERVALS_SECONDS": ""},
        ):
            self.assertEqual(retry_intervals(), [])


class AnalyzeRetryApiTest(unittest.IsolatedAsyncioTestCase):
    @patch("main.record_accepted_analyze_request")
    @patch("main.retry_intervals", return_value=[30, 60, 120])
    @patch("main.q")
    async def test_enqueues_analysis_with_configured_retry(
        self,
        queue: Mock,
        _retry_intervals: Mock,
        _record_accepted: Mock,
    ) -> None:
        from main import analyze

        queue.enqueue.return_value = SimpleNamespace(id="task-id")
        payload = AnalyzeRequest(query="Consulta")
        token_data = SimpleNamespace(
            application_id=UUID("c824bf11-2a72-43dd-919b-a3f76de5fe04"),
            name="Agente WhatsApp",
        )

        await analyze(payload, token_data)

        retry = queue.enqueue.call_args.kwargs["retry"]
        self.assertEqual(retry.max, 3)
        self.assertEqual(retry.intervals, [30, 60, 120])

    @patch("main.record_accepted_analyze_request")
    @patch("main.retry_intervals", return_value=[])
    @patch("main.q")
    async def test_enqueues_analysis_without_retry_when_list_is_empty(
        self,
        queue: Mock,
        _retry_intervals: Mock,
        _record_accepted: Mock,
    ) -> None:
        from main import analyze

        queue.enqueue.return_value = SimpleNamespace(id="task-id")
        payload = AnalyzeRequest(query="Consulta")
        token_data = SimpleNamespace(
            application_id=UUID("c824bf11-2a72-43dd-919b-a3f76de5fe04"),
            name="Agente WhatsApp",
        )

        await analyze(payload, token_data)

        self.assertIsNone(queue.enqueue.call_args.kwargs["retry"])

    @patch("main.Job.fetch")
    async def test_scheduled_retry_is_reported_as_queued(
        self,
        fetch_job: Mock,
    ) -> None:
        from main import get_status

        fetch_job.return_value = SimpleNamespace(
            is_queued=False,
            is_scheduled=True,
            is_started=False,
            is_finished=False,
            is_failed=False,
        )

        response = await get_status("task-id")

        self.assertEqual(response.status, "queued")


class AnalysisWorkerTest(unittest.TestCase):
    @patch("workers.analysis.Worker")
    @patch("workers.analysis.Queue")
    @patch("workers.analysis.Redis.from_url")
    def test_starts_worker_with_scheduler(
        self,
        _redis_from_url: Mock,
        _queue: Mock,
        worker: Mock,
    ) -> None:
        from workers.analysis import main

        main()

        worker.return_value.work.assert_called_once_with(with_scheduler=True)


class AnalyzeRetryTraceTest(unittest.TestCase):
    @patch.dict(os.environ, {"APP_VERSION": "test-version"})
    @patch("jobs.analyze.wait_for_all_tracers")
    @patch("jobs.analyze.workflow.stream", return_value=[])
    @patch("jobs.analyze.get_current_job")
    def test_identifies_retry_in_trace_name_tags_and_metadata(
        self,
        get_current_job: Mock,
        stream: Mock,
        _wait_for_tracers: Mock,
    ) -> None:
        from jobs import process_analyze_job

        get_current_job.return_value = SimpleNamespace(
            id="task-id",
            retry_intervals=[30, 60, 120],
            retries_left=2,
        )

        process_analyze_job("Consulta")

        trace_config = stream.call_args.kwargs["config"]
        self.assertEqual(trace_config["run_name"], "analyze_workflow_retry")
        self.assertEqual(trace_config["tags"], ["flow:analyze", "retry"])
        self.assertEqual(trace_config["metadata"], {
            "task_id": "task-id",
            "app_version": "test-version",
            "retry_attempt": 1,
            "is_retry": True,
        })


if __name__ == "__main__":
    unittest.main()
