"""Penyimpanan MailGuard: SQLite lokal atau Supabase PostgreSQL."""
from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any

from config import get_supabase_config, get_setting

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "mailguard_v2.db"


def get_backend_name() -> str:
    url, key = get_supabase_config()
    if url and key:
        return "Supabase PostgreSQL"
    if url or key:
        return "Konfigurasi Supabase belum lengkap"
    return "SQLite lokal"


def _supabase_enabled() -> bool:
    url, key = get_supabase_config()
    if bool(url) != bool(key):
        raise RuntimeError(
            "Konfigurasi Supabase belum lengkap. Isi SUPABASE_URL dan "
            "SUPABASE_SECRET_KEY (atau SUPABASE_SERVICE_ROLE_KEY), atau hapus keduanya untuk memakai SQLite lokal."
        )
    return bool(url and key)


@lru_cache(maxsize=1)
def _supabase_client():
    url, key = get_supabase_config()
    if not url or not key:
        raise RuntimeError("SUPABASE_URL dan SUPABASE_SECRET_KEY (atau SUPABASE_SERVICE_ROLE_KEY) belum diatur.")
    try:
        from supabase import create_client
    except ImportError as exc:
        raise RuntimeError(
            "Paket supabase belum terpasang. Jalankan: pip install -r requirements.txt"
        ) from exc
    return create_client(url, key)


def get_db_path() -> Path:
    raw_path = get_setting("MAILGUARD_DB_PATH")
    path = Path(str(raw_path)).expanduser() if raw_path else DEFAULT_DB_PATH
    if not path.is_absolute():
        path = (BASE_DIR / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(get_db_path(), timeout=20)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def init_db() -> None:
    if _supabase_enabled():
        # Table must be created using supabase_schema.sql before deploying.
        _supabase_client().table("messages").select("id").limit(1).execute()
        return

    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tracking_hash TEXT,
                sender_name TEXT NOT NULL,
                sender_email TEXT NOT NULL,
                recipient_email TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                predicted_label TEXT NOT NULL CHECK (predicted_label IN ('SPAM', 'HAM')),
                spam_probability REAL NOT NULL,
                ham_probability REAL NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        # Migration aman untuk database SQLite V1 yang mungkin sudah ada.
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(messages)").fetchall()
        }
        if "tracking_hash" not in columns:
            connection.execute("ALTER TABLE messages ADD COLUMN tracking_hash TEXT")
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_tracking_hash "
            "ON messages(tracking_hash) WHERE tracking_hash IS NOT NULL"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_label_created "
            "ON messages(predicted_label, created_at DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at DESC)"
        )


def save_message(
    *,
    tracking_hash: str,
    sender_name: str,
    sender_email: str,
    recipient_email: str,
    subject: str,
    body: str,
    predicted_label: str,
    spam_probability: float,
    ham_probability: float,
    created_at: str,
) -> int | str:
    payload = {
        "tracking_hash": tracking_hash,
        "sender_name": sender_name,
        "sender_email": sender_email,
        "recipient_email": recipient_email,
        "subject": subject,
        "body": body,
        "predicted_label": predicted_label,
        "spam_probability": float(spam_probability),
        "ham_probability": float(ham_probability),
        "created_at": created_at,
    }
    if _supabase_enabled():
        response = _supabase_client().table("messages").insert(payload).select("id").execute()
        rows = response.data or []
        if not rows:
            raise RuntimeError("Database tidak mengembalikan ID email setelah penyimpanan.")
        return rows[0]["id"]

    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO messages (
                tracking_hash, sender_name, sender_email, recipient_email, subject, body,
                predicted_label, spam_probability, ham_probability, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tracking_hash,
                sender_name,
                sender_email,
                recipient_email,
                subject,
                body,
                predicted_label,
                float(spam_probability),
                float(ham_probability),
                created_at,
            ),
        )
        return int(cursor.lastrowid)


def get_message(message_id: int | str) -> dict[str, Any] | None:
    if _supabase_enabled():
        response = (
            _supabase_client().table("messages").select("*").eq("id", message_id).limit(1).execute()
        )
        rows = response.data or []
        return dict(rows[0]) if rows else None

    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM messages WHERE id = ?", (int(message_id),)
        ).fetchone()
    return dict(row) if row else None


def get_message_by_tracking_hash(tracking_hash: str) -> dict[str, Any] | None:
    if _supabase_enabled():
        response = (
            _supabase_client().table("messages").select("*")
            .eq("tracking_hash", tracking_hash).limit(1).execute()
        )
        rows = response.data or []
        return dict(rows[0]) if rows else None

    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM messages WHERE tracking_hash = ? LIMIT 1", (tracking_hash,)
        ).fetchone()
    return dict(row) if row else None


def list_messages(folder: str = "All Mail", search: str = "", limit: int = 500) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 1000))
    if _supabase_enabled():
        query = _supabase_client().table("messages").select("*")
        if folder == "Inbox":
            query = query.eq("predicted_label", "HAM")
        elif folder == "Spam":
            query = query.eq("predicted_label", "SPAM")
        response = query.order("created_at", desc=True).limit(safe_limit).execute()
        rows = [dict(row) for row in (response.data or [])]
    else:
        conditions: list[str] = []
        params: list[Any] = []
        if folder == "Inbox":
            conditions.append("predicted_label = 'HAM'")
        elif folder == "Spam":
            conditions.append("predicted_label = 'SPAM'")
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(safe_limit)
        with connect() as connection:
            result = connection.execute(
                f"SELECT * FROM messages {where_clause} "
                "ORDER BY created_at DESC, id DESC LIMIT ?",
                params,
            ).fetchall()
        rows = [dict(row) for row in result]

    term = search.strip().casefold()
    if term:
        fields = ("sender_name", "sender_email", "recipient_email", "subject", "body")
        rows = [
            row for row in rows
            if any(term in str(row.get(field, "")).casefold() for field in fields)
        ]
    return rows


def get_counts() -> dict[str, int]:
    if _supabase_enabled():
        table = _supabase_client().table("messages")
        total_response = table.select("id", count="exact", head=True).execute()
        ham_response = (
            table.select("id", count="exact", head=True).eq("predicted_label", "HAM").execute()
        )
        spam_response = (
            table.select("id", count="exact", head=True).eq("predicted_label", "SPAM").execute()
        )
        total = int(total_response.count or 0)
        ham = int(ham_response.count or 0)
        spam = int(spam_response.count or 0)
        return {"total": total, "ham": ham, "spam": spam}

    with connect() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN predicted_label = 'HAM' THEN 1 ELSE 0 END) AS ham,
                   SUM(CASE WHEN predicted_label = 'SPAM' THEN 1 ELSE 0 END) AS spam
            FROM messages
            """
        ).fetchone()
    return {key: int(row[key] or 0) for key in ("total", "ham", "spam")}


def delete_message(message_id: int | str) -> None:
    if _supabase_enabled():
        _supabase_client().table("messages").delete().eq("id", message_id).execute()
        return
    with connect() as connection:
        connection.execute("DELETE FROM messages WHERE id = ?", (int(message_id),))
