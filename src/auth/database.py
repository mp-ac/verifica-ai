import sqlite3
from pathlib import Path
from uuid import uuid4

from .config import get_auth_config
from .token_security import hash_token


_REDACTED_TOKEN = "***REDACTED***"


def _create_auth_table(conn: sqlite3.Connection, table_name: str) -> None:
    """Create an authentication table with the current canonical schema."""
    conn.execute(
        f"""
        CREATE TABLE {table_name} (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          application_id TEXT NOT NULL UNIQUE,
          name TEXT NOT NULL,
          token_hash TEXT NOT NULL UNIQUE,
          active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _has_unique_index(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
) -> bool:
    """Return whether a table has a single-column unique index."""
    for index in conn.execute(f"PRAGMA index_list({table_name})"):
        if not index[2]:
            continue
        index_name = str(index[1]).replace('"', '""')
        indexed_columns = [
            row[2]
            for row in conn.execute(f'PRAGMA index_info("{index_name}")')
        ]
        if indexed_columns == [column_name]:
            return True
    return False


def _auth_table_requires_migration(
    conn: sqlite3.Connection,
    columns: set[str],
) -> bool:
    """Return whether the existing token table differs from the target schema."""
    expected_columns = {
        "id",
        "application_id",
        "name",
        "token_hash",
        "active",
        "created_at",
    }
    return (
        columns != expected_columns
        or not _has_unique_index(conn, "allowed_tokens", "application_id")
        or not _has_unique_index(conn, "allowed_tokens", "token_hash")
    )


def _migrate_auth_table(
    conn: sqlite3.Connection,
    columns: set[str],
) -> None:
    """Rebuild a legacy token table without retaining plaintext credentials."""

    def source(column: str, fallback: str = "NULL") -> str:
        """Select an existing column or a safe SQL fallback."""
        return column if column in columns else fallback

    rows = conn.execute(
        f"""
        SELECT
          id,
          {source("application_id")},
          {source("name")},
          {source("token")},
          {source("token_hash")},
          {source("active", "1")},
          {source("created_at", "CURRENT_TIMESTAMP")}
        FROM allowed_tokens
        ORDER BY id
        """
    ).fetchall()

    conn.execute("DROP TABLE IF EXISTS allowed_tokens_migrated")
    _create_auth_table(conn, "allowed_tokens_migrated")

    for (
        token_id,
        application_id,
        name,
        plaintext_token,
        existing_hash,
        active,
        created_at,
    ) in rows:
        token_hash = str(existing_hash or "").strip()
        if not token_hash:
            token_value = str(plaintext_token or "")
            if not token_value or token_value == _REDACTED_TOKEN:
                raise RuntimeError(
                    f"Não foi possível migrar o token {token_id}: "
                    "valor original indisponível."
                )
            token_hash = hash_token(token_value)

        try:
            conn.execute(
                """
                INSERT INTO allowed_tokens_migrated (
                    id,
                    application_id,
                    name,
                    token_hash,
                    active,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    token_id,
                    application_id or str(uuid4()),
                    name or f"Aplicação {token_id}",
                    token_hash,
                    1 if active else 0,
                    created_at,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise RuntimeError(
                f"Não foi possível migrar o token {token_id}: "
                "application_id ou token duplicado."
            ) from exc

    conn.execute("DROP TABLE allowed_tokens")
    conn.execute("ALTER TABLE allowed_tokens_migrated RENAME TO allowed_tokens")


def init_auth_db() -> None:
    """Create or atomically migrate the configured authentication database."""
    db_path = Path(get_auth_config().auth_db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("BEGIN")
        table_exists = conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'allowed_tokens'
            """
        ).fetchone()
        if table_exists is None:
            _create_auth_table(conn, "allowed_tokens")
            conn.commit()
            return

        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(allowed_tokens)")
        }
        if _auth_table_requires_migration(conn, columns):
            _migrate_auth_table(conn, columns)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
