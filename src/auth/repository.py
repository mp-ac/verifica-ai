import sqlite3
from typing import List, Optional
from uuid import uuid4

from fastapi import HTTPException

from .config import get_auth_config
from .models import TokenCreateResponse, TokenResponse
from .token_security import hash_token, token_fingerprint


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
            token_fingerprint=(
                token_fingerprint(token_hash) if token_hash else None
            ),
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
                "SELECT id, application_id, name, token_hash, "
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
        token_hash = hash_token(token)
        try:
            conn = self._connect()
            cursor = conn.execute(
                """
                INSERT INTO allowed_tokens
                    (application_id, name, token_hash, active)
                VALUES (?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    name,
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
                SELECT id, application_id, name, token_hash,
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
        token_hash = hash_token(token)
        try:
            conn = self._connect()
            row = conn.execute(
                """
                SELECT id, application_id, name, token_hash,
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
    """Parse the timestamp format returned by SQLite."""
    from datetime import datetime

    return datetime.fromisoformat(value.replace(" ", "T"))
