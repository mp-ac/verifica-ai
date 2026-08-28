import unittest
from unittest.mock import Mock, patch

from graph.state import FinalAnswerResult
from similarity.schemas import (
    DuplicateAnalysisDecision,
    DuplicateCheckResult,
    RetrievedCandidate,
)


class SimilarityWorkerTest(unittest.TestCase):
    @patch("similarity.check.check_duplicate_analysis")
    @patch("similarity.check.trace")
    def test_advisory_trace_records_safe_candidate_metadata(
        self,
        trace: Mock,
        check_duplicate_analysis: Mock,
    ) -> None:
        from similarity.check import run_duplicate_check

        run = trace.return_value.__enter__.return_value
        check_duplicate_analysis.return_value = DuplicateCheckResult(
            outcome="match",
            candidate_id="candidate-1",
            candidates=[RetrievedCandidate(
                id="candidate-1",
                match_type="semantic",
                rank=1,
                score=12.5,
                text="Pergunta e título genéricos",
            )],
            evaluation=DuplicateAnalysisDecision(
                decision="match",
                candidate_id="candidate-1",
                confidence="high",
                reason="As alegações são equivalentes.",
            ),
        )

        result = run_duplicate_check(
            "Consulta genérica",
            [],
            task_id="task-id",
            retry_attempt=0,
        )

        check_duplicate_analysis.assert_called_once_with(
            "Consulta genérica",
            [],
        )
        self.assertEqual(
            trace.call_args.kwargs["tags"],
            ["flow:duplicate_check", "mode:advisory"],
        )
        self.assertTrue(
            trace.call_args.kwargs["metadata"]["advisory_mode"]
        )
        self.assertNotIn("shadow_mode", trace.call_args.kwargs["metadata"])
        metadata = run.add_metadata.call_args.args[0]
        self.assertEqual(metadata["duplicate_check_outcome"], "match")
        self.assertEqual(metadata["candidate_count"], 1)
        self.assertEqual(metadata["selected_candidate_id"], "candidate-1")
        self.assertEqual(metadata["judge_confidence"], "high")
        self.assertEqual(metadata["candidates"], [{
            "id": "candidate-1",
            "match_type": "semantic",
            "rank": 1,
            "score": 12.5,
        }])
        self.assertNotIn("text", metadata["candidates"][0])
        self.assertNotIn("reason", metadata)
        self.assertEqual(result.outcome, "match")
        self.assertEqual(result.candidate_id, "candidate-1")
        run.end.assert_called_once_with(outputs={"completed": True})

    @patch("similarity.check.check_duplicate_analysis")
    @patch("similarity.check.trace")
    def test_advisory_failure_does_not_interrupt_worker(
        self,
        trace: Mock,
        check_duplicate_analysis: Mock,
    ) -> None:
        from similarity.check import run_duplicate_check

        run = trace.return_value.__enter__.return_value
        check_duplicate_analysis.side_effect = RuntimeError("falha simulada")

        with self.assertLogs("similarity.check", level="WARNING"):
            result = run_duplicate_check(
                "Consulta genérica",
                [],
                task_id="task-id",
                retry_attempt=0,
            )

        self.assertEqual(result.outcome, "unavailable")
        self.assertEqual(result.failure_stage, "worker")
        run.end.assert_called_once_with(
            outputs={"completed": False},
            error="RuntimeError",
        )

    @patch("similarity.check.check_duplicate_analysis")
    @patch("similarity.check.trace", side_effect=RuntimeError("trace offline"))
    def test_trace_failure_does_not_skip_duplicate_check(
        self,
        _trace: Mock,
        check_duplicate_analysis: Mock,
    ) -> None:
        from similarity.check import run_duplicate_check

        check_duplicate_analysis.return_value = DuplicateCheckResult(
            outcome="no_match"
        )

        with self.assertLogs("similarity.check", level="WARNING"):
            result = run_duplicate_check(
                "Consulta genérica",
                [],
                task_id="task-id",
                retry_attempt=0,
            )

        self.assertEqual(result.outcome, "no_match")
        check_duplicate_analysis.assert_called_once_with(
            "Consulta genérica",
            [],
        )

    @patch("jobs.analyze.run_duplicate_check")
    @patch("jobs.analyze.workflow.stream", return_value=[])
    def test_worker_runs_advisory_check_after_workflow_with_final_title(
        self,
        workflow_stream: Mock,
        run_duplicate_check: Mock,
    ) -> None:
        from jobs.analyze import _process_analyze_job

        run_duplicate_check.return_value = DuplicateCheckResult(
            outcome="match",
            candidate_id="candidate-task-id",
            candidates=[RetrievedCandidate(
                id="candidate-task-id",
                match_type="semantic",
                rank=1,
                score=12.5,
                text="Pergunta e título genéricos",
            )],
            evaluation=DuplicateAnalysisDecision(
                decision="match",
                candidate_id="candidate-task-id",
                confidence="high",
                reason="As alegações são equivalentes.",
            ),
        )

        workflow_stream.return_value = [{
            "router": {
                "final_answer": FinalAnswerResult(
                    title="FALSO: Consulta processada do áudio",
                    answer="Resposta final",
                ),
            },
        }]

        result = _process_analyze_job(
            None,
            [{"type": "audio", "url": "https://example.test/audio.ogg"}],
            task_id="task-id",
            retry_attempt=0,
        )

        run_duplicate_check.assert_called_once_with(
            "Consulta processada do áudio",
            [],
            task_id="task-id",
            retry_attempt=0,
        )
        workflow_stream.assert_called_once()
        self.assertEqual(result["status"], "done")
        self.assertEqual(result["duplicate_check"], {
            "outcome": "match",
            "candidate_task_id": "candidate-task-id",
            "match_type": "semantic",
            "confidence": "high",
        })

    @patch("jobs.analyze.run_duplicate_check")
    @patch("jobs.analyze.workflow.stream", return_value=[])
    def test_worker_skips_duplicate_query_without_final_answer(
        self,
        workflow_stream: Mock,
        run_duplicate_check: Mock,
    ) -> None:
        from jobs.analyze import _process_analyze_job

        run_duplicate_check.return_value = DuplicateCheckResult(
            outcome="skipped"
        )

        result = _process_analyze_job(
            "Consulta sem resultado",
            [],
            task_id="task-id",
            retry_attempt=0,
        )

        workflow_stream.assert_called_once()
        run_duplicate_check.assert_called_once_with(
            None,
            [],
            task_id="task-id",
            retry_attempt=0,
        )
        self.assertEqual(result["duplicate_check"]["outcome"], "skipped")


if __name__ == "__main__":
    unittest.main()
