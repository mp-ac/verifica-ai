import hashlib
import sqlite3
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from fastapi import HTTPException

from .config import get_auth_config
from .models import TokenCreateResponse, TokenResponse


def _hash_token(token: str) -> str:
    """Return the SHA-256 hex digest of a token string."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _mask_token(token_hash: str) -> str:
    """Return a masked preview of a token hash (first 4 + last 4 chars)."""
    if len(token_hash) <= 8:
        return token_hash[:2] + "***"
    return token_hash[:4] + "..." + token_hash[-4:]


def init_auth_db() -> None:
    db_path = Path(get_auth_config().auth_db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS allowed_tokens (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              application_id TEXT NOT NULL UNIQUE,
              name TEXT NOT NULL,
              token TEXT NOT NULL UNIQUE,
              active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(allowed_tokens)")
        }
        if "application_id" not in columns:
            conn.execute(
                "ALTER TABLE allowed_tokens ADD COLUMN application_id TEXT"
            )
        if "name" not in columns:
            conn.execute("ALTER TABLE allowed_tokens ADD COLUMN name TEXT")

        # --- SEC-01: add token_hash column and migrate plaintext tokens ---
        if "token_hash" not in columns:
            conn.execute(
                "ALTER TABLE allowed_tokens ADD COLUMN token_hash TEXT"
            )

        legacy_tokens = conn.execute(
            "SELECT id, application_id, name, token, token_hash "
            "FROM allowed_tokens"
        ).fetchall()
        for token_id, application_id, name, token_value, token_hash in legacy_tokens:
            updates: dict[str, object] = {}

            if not application_id:
                updates["application_id"] = str(uuid4())
            if not name:
                updates["name"] = f"Aplicação {token_id}"

            # Migrate plaintext tokens: if token_hash is empty the token
            # column still holds the original plaintext value.
            if not token_hash and token_value:
                updates["token_hash"] = _hash_token(token_value)
                # Overwrite plaintext token with a redacted marker so it
                # cannot be recovered from the database.
                updates["token"] = "***REDACTED***"

            if updates:
                set_clause = ", ".join(f"{k} = ?" for k in updates)
                conn.execute(
                    f"UPDATE allowed_tokens SET {set_clause} WHERE id = ?",
                    (*updates.values(), token_id),
                )

        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            allowed_tokens_application_id_unique
            ON allowed_tokens (application_id)
            """
        )
        conn.commit()
    finally:
        conn.close()


class TokenRepository:
    def __init__(self) -> None:
        self._db_path = get_auth_config().auth_db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_token_response(self, row: sqlite3.Row) -> TokenResponse:
        token_hash = row["token_hash"] or ""
        return TokenResponse(
            id=row["id"],
            application_id=row["application_id"],
            name=row["name"],
            token_preview=_mask_token(token_hash) if token_hash else None,
            active=bool(row["active"]),
            created_at=datetime_from_sqlite(row["created_at"]),
        )

    def list_tokens(
        self,
        active: Optional[bool],
        limit: int,
        offset: int,
    ) -> List[TokenResponse]:
        conn = None
        try:
            conn = self._connect()
            query = (
                "SELECT id, application_id, name, token, token_hash, "
                "active, created_at "
                "FROM allowed_tokens"
            )
            params: list[object] = []
            if active is not None:
                query += " WHERE active = ?"
                params.append(1 if active else 0)
            query += " ORDER BY id DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_token_response(row) for row in rows]
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="Erro ao listar tokens")
        finally:
            if conn is not None:
                conn.close()

    def create_token(
        self,
        name: str,
        token: str,
        active: bool,
    ) -> TokenCreateResponse:
        conn = None
        token_hash = _hash_token(token)
        try:
            conn = self._connect()
            cursor = conn.execute(
                """
                INSERT INTO allowed_tokens
                    (application_id, name, token, token_hash, active)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    name,
                    "***REDACTED***",
                    token_hash,
                    1 if active else 0,
                ),
            )
            conn.commit()
            token_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Token já existe")
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="Erro ao criar token")
        finally:
            if conn is not None:
                conn.close()
        base = self.get_token(token_id)
        return TokenCreateResponse(
            **base.model_dump(),
            token=token,
        )

    def update_token(
        self,
        token_id: int,
        *,
        name: str | None = None,
        active: bool | None = None,
    ) -> TokenResponse:
        conn = None
        try:
            conn = self._connect()
            updates: list[str] = []
            params: list[object] = []
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if active is not None:
                updates.append("active = ?")
                params.append(1 if active else 0)
            if not updates:
                return self.get_token(token_id)
            params.append(token_id)
            cursor = conn.execute(
                f"UPDATE allowed_tokens SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Token não encontrado")
        except HTTPException:
            raise
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="Erro ao atualizar token")
        finally:
            if conn is not None:
                conn.close()
        return self.get_token(token_id)

    def delete_token(self, token_id: int) -> None:
        conn = None
        try:
            conn = self._connect()
            cursor = conn.execute(
                "DELETE FROM allowed_tokens WHERE id = ?",
                (token_id,),
            )
            conn.commit()
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Token não encontrado")
        except HTTPException:
            raise
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="Erro ao remover token")
        finally:
            if conn is not None:
                conn.close()

    def get_token(self, token_id: int) -> TokenResponse:
        conn = None
        try:
            conn = self._connect()
            row = conn.execute(
                """
                SELECT id, application_id, name, token, token_hash,
                       active, created_at
                FROM allowed_tokens
                WHERE id = ?
                """,
                (token_id,),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Token não encontrado")
            return self._row_to_token_response(row)
        except HTTPException:
            raise
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="Erro ao buscar token")
        finally:
            if conn is not None:
                conn.close()

    def get_token_by_value(self, token: str) -> Optional[TokenResponse]:
        """Look up an active token by its SHA-256 hash."""
        conn = None
        token_hash = _hash_token(token)
        try:
            conn = self._connect()
            row = conn.execute(
                """
                SELECT id, application_id, name, token, token_hash,
                       active, created_at
                FROM allowed_tokens
                WHERE token_hash = ? AND active = 1
                """,
                (token_hash,),
            ).fetchone()
            if row is None:
                return None
            return self._row_to_token_response(row)
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="Erro ao buscar token")
        finally:
            if conn is not None:
                conn.close()


def datetime_from_sqlite(value: str):
    from datetime import datetime

    return datetime.fromisoformat(value.replace(" ", "T"))
