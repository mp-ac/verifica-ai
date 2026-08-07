import sqlite3
import tempfile
import unittest
from pathlib import Path
from uuid import UUID

from auth.config import AuthConfig, configure_auth
from auth.repository import TokenRepository, init_auth_db


class TokenRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "auth.sqlite3"
        configure_auth(AuthConfig(auth_db_path=str(self.db_path), admin_tokens=set()))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_creates_named_application_identity_for_token(self) -> None:
        init_auth_db()
        token = TokenRepository().create_token(
            name="Agente WhatsApp",
            token="secret-token",
            active=True,
        )

        self.assertEqual(token.name, "Agente WhatsApp")
        self.assertEqual(token.token, "secret-token")
        self.assertIsInstance(token.application_id, UUID)

        authenticated = TokenRepository().get_token_by_value("secret-token")
        self.assertIsNotNone(authenticated)
        self.assertEqual(authenticated.application_id, token.application_id)
        self.assertEqual(authenticated.name, "Agente WhatsApp")

    def test_migrates_existing_tokens_with_application_identity(self) -> None:
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
        connection.execute(
            "INSERT INTO allowed_tokens (token, active) VALUES (?, ?)",
            ("legacy-token", 1),
        )
        connection.commit()
        connection.close()

        init_auth_db()

        token = TokenRepository().get_token_by_value("legacy-token")
        self.assertIsNotNone(token)
        self.assertEqual(token.name, "Aplicação 1")
        self.assertIsInstance(token.application_id, UUID)

    def test_updates_application_name_without_changing_identity(self) -> None:
        init_auth_db()
        repo = TokenRepository()
        token = repo.create_token("Nome antigo", "secret-token", True)

        updated = repo.update_token(token.id, name="Agente WhatsApp")

        self.assertEqual(updated.application_id, token.application_id)
        self.assertEqual(updated.name, "Agente WhatsApp")
        self.assertTrue(updated.active)


if __name__ == "__main__":
    unittest.main()
