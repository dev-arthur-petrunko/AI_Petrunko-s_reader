"""База знань — сховище SQLite для завантажених документів з автоочищенням."""

import os
import time
import sqlite3
import logging
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

MAX_AGE_DAYS = 30


def _pick_writable_dir() -> str:
    """Вибирає записувану директорію для БД: KB_DB_DIR → проєкт → тимчасова папка."""
    candidates = []
    if os.environ.get("KB_DB_DIR"):
        candidates.append(os.environ["KB_DB_DIR"])
    candidates.append(os.path.abspath("."))
    candidates.append(os.path.join(tempfile.gettempdir(), "kb_data"))
    for d in candidates:
        try:
            os.makedirs(d, exist_ok=True)
            probe = os.path.join(d, ".wtest")
            with open(probe, "w") as f:
                f.write("x")
            os.unlink(probe)
            return d
        except OSError:
            continue
    return tempfile.gettempdir()


DB_DIR = _pick_writable_dir()
DB_PATH = os.path.join(DB_DIR, "knowledge_base.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            format TEXT NOT NULL DEFAULT 'txt',
            word_count INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL,
            last_accessed REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    logger.info("Knowledge base initialized at %s", DB_PATH)


def cleanup_stale(max_age_days: int = MAX_AGE_DAYS) -> int:
    conn = _get_conn()
    cutoff = time.time() - (max_age_days * 86400)
    cur = conn.execute("DELETE FROM documents WHERE last_accessed < ?", (cutoff,))
    removed = cur.rowcount
    conn.commit()
    conn.close()
    if removed:
        logger.info("KB cleanup: removed %d documents older than %d days", removed, max_age_days)
    return removed


def add_document(title: str, content: str, fmt: str = "txt") -> int:
    word_count = len(content.split())
    now = time.time()
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO documents (title, content, format, word_count, created_at, last_accessed) VALUES (?, ?, ?, ?, ?, ?)",
        (title, content, fmt, word_count, now, now),
    )
    doc_id = cur.lastrowid
    conn.commit()
    conn.close()
    return doc_id


def list_documents() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, title, word_count, created_at FROM documents ORDER BY last_accessed DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_document(doc_id: int) -> Optional[dict]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if row:
        conn.execute(
            "UPDATE documents SET last_accessed = ? WHERE id = ?",
            (time.time(), doc_id),
        )
        conn.commit()
    conn.close()
    return dict(row) if row else None


def delete_document(doc_id: int) -> bool:
    conn = _get_conn()
    cur = conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def search_documents(query: str) -> list[dict]:
    conn = _get_conn()
    pattern = f"%{query}%"
    rows = conn.execute(
        "SELECT id, title, word_count FROM documents WHERE title LIKE ? OR content LIKE ? ORDER BY last_accessed DESC",
        (pattern, pattern),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
