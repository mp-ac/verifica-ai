import sqlite3
import tempfile
import unittest
from pathlib import Path
from uuid import UUID

from auth.config import AuthConfig, configure_auth
from auth.database import init_auth_db
from auth.repository import TokenRepository
from auth.token_security import hash_token


class AuthDatabaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "auth.sqlite3"
        configure_auth(AuthConfig(auth_db_path=str(self.db_path), admin_tokens=set()))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_migrates_multiple_legacy_tokens(self) -> None:
        connection = sqlite3.connect(self.db_path)
        connection.execute(
            """
            CREATE TABLE allowed_tokens (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              token TEXT NOT NULL UNIQUE,
              active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.executemany(
            "INSERT INTO allowed_tokens (token, active) VALUES (?, ?)",
            [("legacy-token-one", 1), ("legacy-token-two", 1)],
        )
        connection.commit()
        connection.close()

        init_auth_db()

        repo = TokenRepository()
        first = repo.get_token_by_value("legacy-token-one")
        second = repo.get_token_by_value("legacy-token-two")
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(first.name, "Aplicação 1")
        self.assertEqual(second.name, "Aplicação 2")
        self.assertIsInstance(first.application_id, UUID)
        self.assertIsInstance(second.application_id, UUID)

        conn = sqlite3.connect(self.db_path)
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(allowed_tokens)")
        }
        hashes = conn.execute(
            "SELECT token_hash FROM allowed_tokens ORDER BY id"
        ).fetchall()
        conn.close()

        self.assertNotIn("token", columns)
        self.assertEqual(
            hashes,
            [
                (hash_token("legacy-token-one"),),
                (hash_token("legacy-token-two"),),
            ],
        )

    def test_migrates_schema_previously_changed_by_pull_request(self) -> None:
        application_id = "4ec9a091-c4e2-4609-aa0c-e37906c42f1e"
        plaintext_token = "h" * 32
        connection = sqlite3.connect(self.db_path)
        connection.execute(
            """
            CREATE TABLE allowed_tokens (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              application_id TEXT NOT NULL UNIQUE,
              name TEXT NOT NULL,
              token TEXT NOT NULL UNIQUE,
              token_hash TEXT,
              active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            INSERT INTO allowed_tokens (
                application_id,
                name,
                token,
                token_hash,
                active
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                application_id,
                "Partially Migrated App",
                "***REDACTED***",
                hash_token(plaintext_token),
                1,
            ),
        )
        connection.commit()
        connection.close()

        init_auth_db()

        migrated = TokenRepository().get_token_by_value(plaintext_token)
        self.assertIsNotNone(migrated)
        self.assertEqual(str(migrated.application_id), application_id)
        self.assertEqual(migrated.name, "Partially Migrated App")

        conn = sqlite3.connect(self.db_path)
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(allowed_tokens)")
        }
        conn.close()
        self.assertNotIn("token", columns)

    def test_database_initialization_is_idempotent(self) -> None:
        init_auth_db()
        plaintext_token = "i" * 32
        TokenRepository().create_token("Idempotent App", plaintext_token, True)

        init_auth_db()

        found = TokenRepository().get_token_by_value(plaintext_token)
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "Idempotent App")

    def test_migration_rolls_back_when_token_hash_is_duplicated(self) -> None:
        duplicate_hash = hash_token("duplicated-token")
        connection = sqlite3.connect(self.db_path)
        connection.execute(
            """
            CREATE TABLE allowed_tokens (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              application_id TEXT NOT NULL UNIQUE,
              name TEXT NOT NULL,
              token TEXT NOT NULL UNIQUE,
              token_hash TEXT,
              active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO allowed_tokens (
                application_id,
                name,
                token,
                token_hash
            )
            VALUES (?, ?, ?, ?)
            """,
            [
                (str(UUID(int=1)), "First App", "first-token", duplicate_hash),
                (str(UUID(int=2)), "Second App", "second-token", duplicate_hash),
            ],
        )
        connection.commit()
        connection.close()

        with self.assertRaises(RuntimeError):
            init_auth_db()

        conn = sqlite3.connect(self.db_path)
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(allowed_tokens)")
        }
        row_count = conn.execute(
            "SELECT COUNT(*) FROM allowed_tokens"
        ).fetchone()[0]
        conn.close()
        self.assertIn("token", columns)
        self.assertEqual(row_count, 2)


if __name__ == "__main__":
    unittest.main()
