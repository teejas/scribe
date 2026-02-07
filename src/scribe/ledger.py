import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path.home() / ".scribe" / "processed.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS processed (
    file_path    TEXT PRIMARY KEY,
    status       TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    completed_at TEXT,
    error        TEXT
);
"""


class Ledger:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_SCHEMA)
        self._conn.commit()
        # Restrict permissions: owner read/write only
        db_path.chmod(0o600)

    def is_processed(self, file_path: str) -> bool:
        row = self._conn.execute(
            "SELECT status FROM processed WHERE file_path = ?", (file_path,)
        ).fetchone()
        return row is not None and row["status"] == "done"

    def is_known(self, file_path: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM processed WHERE file_path = ?", (file_path,)
        ).fetchone()
        return row is not None

    def mark_pending(self, file_path: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT OR IGNORE INTO processed (file_path, status, created_at) VALUES (?, 'pending', ?)",
            (file_path, now),
        )
        self._conn.commit()

    def mark_processing(self, file_path: str) -> None:
        self._conn.execute(
            "UPDATE processed SET status = 'processing' WHERE file_path = ?",
            (file_path,),
        )
        self._conn.commit()

    def mark_done(self, file_path: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE processed SET status = 'done', completed_at = ?, error = NULL WHERE file_path = ?",
            (now, file_path),
        )
        self._conn.commit()

    def mark_failed(self, file_path: str, error: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE processed SET status = 'failed', completed_at = ?, error = ? WHERE file_path = ?",
            (now, error, file_path),
        )
        self._conn.commit()

    def get_failed(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT file_path FROM processed WHERE status = 'failed'"
        ).fetchall()
        return [r["file_path"] for r in rows]

    def reset_failed(self) -> int:
        cursor = self._conn.execute(
            "UPDATE processed SET status = 'pending', completed_at = NULL, error = NULL WHERE status = 'failed'"
        )
        self._conn.commit()
        return cursor.rowcount

    def get_pending(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT file_path FROM processed WHERE status = 'pending'"
        ).fetchall()
        return [r["file_path"] for r in rows]

    def close(self) -> None:
        self._conn.close()
