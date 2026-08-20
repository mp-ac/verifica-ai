import unittest
from unittest.mock import Mock, patch

from similarity.schemas import (
    DuplicateAnalysisDecision,
    DuplicateCheckResult,
    RetrievedCandidate,
)


class SimilarityWorkerTest(unittest.TestCase):
    @patch("similarity.shadow.check_duplicate_analysis")
    @patch("similarity.shadow.trace")
    def test_shadow_trace_records_safe_candidate_metadata(
        self,
        trace: Mock,
        check_duplicate_analysis: Mock,
    ) -> None:
        from similarity.shadow import run_duplicate_check_shadow

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

        run_duplicate_check_shadow(
            "Consulta genérica",
            [],
            task_id="task-id",
            retry_attempt=0,
        )

        check_duplicate_analysis.assert_called_once_with(
            "Consulta genérica",
            [],
        )
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
        run.end.assert_called_once_with(outputs={"completed": True})

    @patch("similarity.shadow.check_duplicate_analysis")
    @patch("similarity.shadow.trace")
    def test_shadow_failure_does_not_interrupt_worker(
        self,
        trace: Mock,
        check_duplicate_analysis: Mock,
    ) -> None:
        from similarity.shadow import run_duplicate_check_shadow

        run = trace.return_value.__enter__.return_value
        check_duplicate_analysis.side_effect = RuntimeError("falha simulada")

        with self.assertLogs("similarity.shadow", level="WARNING"):
            result = run_duplicate_check_shadow(
                "Consulta genérica",
                [],
                task_id="task-id",
                retry_attempt=0,
            )

        self.assertIsNone(result)
        run.end.assert_called_once_with(
            outputs={"completed": False},
            error="RuntimeError",
        )

    @patch("jobs.analyze.run_duplicate_check_shadow")
    @patch("jobs.analyze.workflow.stream", return_value=[])
    def test_worker_runs_shadow_check_and_continues_workflow(
        self,
        workflow_stream: Mock,
        run_duplicate_check_shadow: Mock,
    ) -> None:
        from jobs.analyze import _process_analyze_job

        result = _process_analyze_job(
            "Consulta genérica",
            [],
            task_id="task-id",
            retry_attempt=0,
        )

        run_duplicate_check_shadow.assert_called_once_with(
            "Consulta genérica",
            [],
            task_id="task-id",
            retry_attempt=0,
        )
        workflow_stream.assert_called_once()
        self.assertEqual(result["status"], "done")


if __name__ == "__main__":
    unittest.main()
