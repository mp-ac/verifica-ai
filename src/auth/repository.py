import sqlite3
from pathlib import Path
from typing import List, Optional

from fastapi import HTTPException

from .config import get_auth_config
from .models import TokenResponse


def init_auth_db() -> None:
    db_path = Path(get_auth_config().auth_db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS allowed_tokens (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              token TEXT NOT NULL UNIQUE,
              active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
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
        return TokenResponse(
            id=row["id"],
            token=row["token"],
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
            query = "SELECT id, token, active, created_at FROM allowed_tokens"
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

    def create_token(self, token: str, active: bool) -> TokenResponse:
        conn = None
        try:
            conn = self._connect()
            cursor = conn.execute(
                "INSERT INTO allowed_tokens (token, active) VALUES (?, ?)",
                (token, 1 if active else 0),
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
        return self.get_token(token_id)

    def set_active(self, token_id: int, active: bool) -> TokenResponse:
        conn = None
        try:
            conn = self._connect()
            cursor = conn.execute(
                "UPDATE allowed_tokens SET active = ? WHERE id = ?",
                (1 if active else 0, token_id),
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
                "SELECT id, token, active, created_at FROM allowed_tokens WHERE id = ?",
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
        conn = None
        try:
            conn = self._connect()
            row = conn.execute(
                """
                SELECT id, token, active, created_at
                FROM allowed_tokens
                WHERE token = ? AND active = 1
                """,
                (token,),
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
