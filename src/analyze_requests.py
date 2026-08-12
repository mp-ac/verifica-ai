import os
import sqlite3
from pathlib import Path
from uuid import UUID


def analyze_requests_db_path() -> str:
    """Return the SQLite path used by accepted analyze request records."""
    return os.getenv(
        "ANALYZE_REQUESTS_DB_PATH",
        "db/analyze_requests.sqlite3",
    )


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(analyze_requests_db_path(), timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def init_analyze_requests_db() -> None:
    """Create the storage used for successfully accepted analyze requests."""
    db_path = Path(analyze_requests_db_path())
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = _connect()
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS analyze_requests (
              task_id TEXT PRIMARY KEY,
              application_id TEXT NOT NULL,
              application_name TEXT NOT NULL,
              accepted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS analyze_requests_accepted_at_idx
            ON analyze_requests (accepted_at)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS analyze_requests_application_id_idx
            ON analyze_requests (application_id)
            """
        )
        connection.commit()
    finally:
        connection.close()


def record_accepted_analyze_request(
    *,
    task_id: str,
    application_id: UUID,
    application_name: str,
) -> None:
    """Record an authenticated request after RQ generated its task ID."""
    connection = _connect()
    try:
        connection.execute(
            """
            INSERT INTO analyze_requests (
              task_id,
              application_id,
              application_name
            ) VALUES (?, ?, ?)
            """,
            (task_id, str(application_id), application_name),
        )
        connection.commit()
    finally:
        connection.close()


def list_accepted_analyze_requests(
    *,
    application_id: UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    """List accepted requests and their total count for admin inspection."""
    where = ""
    params: list[object] = []
    if application_id is not None:
        where = " WHERE application_id = ?"
        params.append(str(application_id))

    connection = _connect()
    try:
        total = connection.execute(
            f"SELECT COUNT(*) FROM analyze_requests{where}",
            params,
        ).fetchone()[0]
        rows = connection.execute(
            "SELECT task_id, application_id, application_name, accepted_at "
            f"FROM analyze_requests{where} "
            "ORDER BY accepted_at DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        return [dict(row) for row in rows], total
    finally:
        connection.close()
