import sqlite3
import tempfile
import unittest
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException

from auth.config import AuthConfig, configure_auth
from auth.database import init_auth_db
from auth.models import TokenResponse
from auth.repository import TokenRepository
from auth.token_security import hash_token


class TokenRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "auth.sqlite3"
        configure_auth(AuthConfig(auth_db_path=str(self.db_path), admin_tokens=set()))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_creates_named_application_identity_for_token(self) -> None:
        init_auth_db()
        plaintext_token = "a" * 32

        token = TokenRepository().create_token(
            name="Agente WhatsApp",
            token=plaintext_token,
            active=True,
        )

        self.assertEqual(token.name, "Agente WhatsApp")
        self.assertEqual(token.token, plaintext_token)
        self.assertIsInstance(token.application_id, UUID)

        authenticated = TokenRepository().get_token_by_value(plaintext_token)
        self.assertIsNotNone(authenticated)
        self.assertEqual(authenticated.application_id, token.application_id)
        self.assertEqual(authenticated.name, "Agente WhatsApp")
        self.assertNotIn("token", TokenResponse.model_fields)

    def test_token_stored_as_hash_without_plaintext_column(self) -> None:
        init_auth_db()
        plaintext_token = "b" * 32
        TokenRepository().create_token(
            name="Test App",
            token=plaintext_token,
            active=True,
        )

        conn = sqlite3.connect(self.db_path)
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(allowed_tokens)")
        }
        row = conn.execute(
            "SELECT token_hash FROM allowed_tokens WHERE id = 1"
        ).fetchone()
        conn.close()

        self.assertNotIn("token", columns)
        self.assertEqual(row[0], hash_token(plaintext_token))

    def test_creates_and_authenticates_multiple_tokens(self) -> None:
        init_auth_db()
        repo = TokenRepository()
        first_token = "c" * 32
        second_token = "d" * 32

        first = repo.create_token("First App", first_token, True)
        second = repo.create_token("Second App", second_token, True)

        self.assertNotEqual(first.id, second.id)
        self.assertEqual(repo.get_token_by_value(first_token).name, "First App")
        self.assertEqual(repo.get_token_by_value(second_token).name, "Second App")
        self.assertEqual(
            len(repo.list_tokens(active=None, limit=10, offset=0)),
            2,
        )

    def test_rejects_duplicate_token_hash(self) -> None:
        init_auth_db()
        repo = TokenRepository()
        plaintext_token = "e" * 32
        repo.create_token("First App", plaintext_token, True)

        with self.assertRaises(HTTPException) as context:
            repo.create_token("Second App", plaintext_token, True)

        self.assertEqual(context.exception.status_code, 409)

    def test_get_token_by_value_uses_hash(self) -> None:
        init_auth_db()
        repo = TokenRepository()
        plaintext_token = "f" * 32
        repo.create_token(name="App", token=plaintext_token, active=True)

        found = repo.get_token_by_value(plaintext_token)
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "App")
        self.assertIsNone(repo.get_token_by_value("wrong-token"))

    def test_token_fingerprint_is_derived_from_hash(self) -> None:
        init_auth_db()
        repo = TokenRepository()
        plaintext_token = "g" * 32
        created = repo.create_token("Fingerprint", plaintext_token, True)

        self.assertIsNotNone(created.token_fingerprint)
        self.assertIn("...", created.token_fingerprint)
        self.assertNotEqual(
            created.token_fingerprint,
            hash_token(plaintext_token),
        )
        self.assertNotIn(plaintext_token, created.token_fingerprint)

    def test_updates_application_name_without_changing_identity(self) -> None:
        init_auth_db()
        repo = TokenRepository()
        token = repo.create_token("Nome antigo", "j" * 32, True)

        updated = repo.update_token(token.id, name="Agente WhatsApp")

        self.assertEqual(updated.application_id, token.application_id)
        self.assertEqual(updated.name, "Agente WhatsApp")
        self.assertTrue(updated.active)


if __name__ == "__main__":
    unittest.main()
