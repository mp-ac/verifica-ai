import os
import unittest
from unittest.mock import Mock, patch

from graph.state import FinalAnswerResult
from similarity.schemas import DuplicateCheckResult


class AnalysisLimitationsTest(unittest.TestCase):
    def test_old_results_default_to_empty_limitations(self) -> None:
        result = FinalAnswerResult(answer="Resposta anterior")
        self.assertEqual(result.limitations, [])

    @patch.dict(os.environ, {
        "FINAL_RESULTS_API_URL": "https://panel.test/api/v1/final-results",
        "FINAL_RESULTS_API_TOKEN": "test-token",
    })
    @patch("final_results._trace_panel_delivery")
    @patch("final_results.requests.post")
    @patch("jobs.analyze.get_current_job", return_value=None)
    @patch("jobs.analyze.dispatch_completed_result")
    @patch("jobs.analyze.run_duplicate_check")
    @patch("jobs.analyze.workflow.stream")
    def test_analysis_delivers_limitations_separately(
        self, stream: Mock, duplicate_check: Mock, dispatch: Mock,
        _job: Mock, post: Mock, _trace: Mock,
    ) -> None:
        from final_results import store_final_result_job
        from jobs.analyze import process_analyze_job

        answer = "A análise é inconclusiva.\n\nNão foi possível confirmar a data."
        limitations = ["O documento original não estava acessível."]
        stream.return_value = [{"synthesize": {
            "final_answer": FinalAnswerResult(
                answer=answer, classification="inconclusivo",
                limitations=limitations,
            ),
        }}]
        duplicate_check.return_value = DuplicateCheckResult(outcome="skipped")

        result = process_analyze_job("Qual a data do acontecimento?")
        completed = dispatch.call_args.kwargs["completed_result"]
        store_final_result_job("task-id", completed)

        for final in (
            result["final_answer"],
            post.call_args.kwargs["json"]["result"]["final_answer"],
        ):
            self.assertEqual(final["answer"], answer)
            self.assertEqual(final["limitations"], limitations)
            self.assertEqual(final["classification"], "inconclusivo")
