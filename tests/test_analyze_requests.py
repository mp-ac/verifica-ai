import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from analyze_requests import (
    init_analyze_requests_db,
    list_accepted_analyze_requests,
    record_accepted_analyze_request,
)


class AnalyzeRequestsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "analyze_requests.sqlite3"
        self.env = patch.dict(
            os.environ,
            {"ANALYZE_REQUESTS_DB_PATH": str(self.db_path)},
        )
        self.env.start()
        init_analyze_requests_db()

    def tearDown(self) -> None:
        self.env.stop()
        self.temp_dir.cleanup()

    def test_records_only_acceptance_metadata(self) -> None:
        application_id = UUID("c824bf11-2a72-43dd-919b-a3f76de5fe04")

        record_accepted_analyze_request(
            task_id="task-id",
            application_id=application_id,
            application_name="Agente WhatsApp",
        )

        connection = sqlite3.connect(self.db_path)
        try:
            columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(analyze_requests)"
                )
            }
        finally:
            connection.close()

        self.assertEqual(columns, {
            "task_id",
            "application_id",
            "application_name",
            "accepted_at",
        })

        items, total = list_accepted_analyze_requests(
            application_id=None,
            limit=50,
            offset=0,
        )
        self.assertEqual(total, 1)
        self.assertEqual(items[0]["task_id"], "task-id")
        self.assertEqual(items[0]["application_id"], str(application_id))
        self.assertEqual(items[0]["application_name"], "Agente WhatsApp")

    def test_filters_records_by_authenticated_application(self) -> None:
        first_application = UUID("c824bf11-2a72-43dd-919b-a3f76de5fe04")
        second_application = UUID("66c97611-3931-4f96-b963-17f5121b2353")
        record_accepted_analyze_request(
            task_id="first-task",
            application_id=first_application,
            application_name="Primeira aplicação",
        )
        record_accepted_analyze_request(
            task_id="second-task",
            application_id=second_application,
            application_name="Segunda aplicação",
        )

        items, total = list_accepted_analyze_requests(
            application_id=second_application,
            limit=50,
            offset=0,
        )

        self.assertEqual(total, 1)
        self.assertEqual([item["task_id"] for item in items], ["second-task"])


if __name__ == "__main__":
    unittest.main()
