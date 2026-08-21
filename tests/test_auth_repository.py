import sqlite3
import tempfile
import unittest
from pathlib import Path
from uuid import UUID

from auth.config import AuthConfig, configure_auth
from auth.models import TokenResponse
from auth.repository import TokenRepository, _hash_token, init_auth_db


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
        # The plaintext token is returned on creation.
        self.assertEqual(token.token, "secret-token")
        self.assertIsInstance(token.application_id, UUID)

        authenticated = TokenRepository().get_token_by_value("secret-token")
        self.assertIsNotNone(authenticated)
        self.assertEqual(authenticated.application_id, token.application_id)
        self.assertEqual(authenticated.name, "Agente WhatsApp")
        # TokenResponse (from lookup) does NOT have a token field —
        # only TokenCreateResponse (from creation) includes it.
        self.assertFalse(hasattr(TokenResponse, 'model_fields') and 'token' in TokenResponse.model_fields)

    def test_token_stored_as_hash_not_plaintext(self) -> None:
        """SEC-01: verify plaintext token is never stored in the database."""
        init_auth_db()
        TokenRepository().create_token(
            name="Test App",
            token="my-secret-value",
            active=True,
        )

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT token, token_hash FROM allowed_tokens WHERE id = 1"
        ).fetchone()
        conn.close()

        # The `token` column must NOT contain the plaintext value.
        self.assertNotEqual(row["token"], "my-secret-value")
        self.assertEqual(row["token"], "***REDACTED***")
        # The `token_hash` column must contain the SHA-256 hex digest.
        self.assertEqual(row["token_hash"], _hash_token("my-secret-value"))

    def test_get_token_by_value_uses_hash(self) -> None:
        """SEC-01: validate lookup uses hash comparison."""
        init_auth_db()
        repo = TokenRepository()
        repo.create_token(name="App", token="lookup-test-token", active=True)

        found = repo.get_token_by_value("lookup-test-token")
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "App")

        not_found = repo.get_token_by_value("wrong-token")
        self.assertIsNone(not_found)

    def test_token_preview_is_masked(self) -> None:
        """SEC-01: token_preview shows masked hash."""
        init_auth_db()
        repo = TokenRepository()
        created = repo.create_token(name="Preview", token="preview-tok", active=True)

        self.assertIsNotNone(created.token_preview)
        # Preview should contain "..." and be much shorter than the hash.
        self.assertIn("...", created.token_preview)
        # The preview must NOT contain the full hash or plaintext.
        self.assertNotEqual(created.token_preview, _hash_token("preview-tok"))

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

        # After migration, the token should be found by its hash.
        token = TokenRepository().get_token_by_value("legacy-token")
        self.assertIsNotNone(token)
        self.assertEqual(token.name, "Aplicação 1")
        self.assertIsInstance(token.application_id, UUID)

        # Verify the plaintext was redacted in the database.
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT token, token_hash FROM allowed_tokens WHERE id = 1"
        ).fetchone()
        conn.close()
        self.assertEqual(row["token"], "***REDACTED***")
        self.assertEqual(row["token_hash"], _hash_token("legacy-token"))

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
