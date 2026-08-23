"""SQLite persistence for subscriptions and watched emails.

One file, no server to run — enough for the volume this bot will see
before it needs anything heavier.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta

DB_PATH = "subscriptions.db"


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS subscriptions (
                chat_id INTEGER PRIMARY KEY,
                plan TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                expiry_notified INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watched_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                last_breaches TEXT NOT NULL DEFAULT '[]',
                UNIQUE(chat_id, email)
            )
            """
        )


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert_subscription(chat_id: int, plan: str, days: int) -> str:
    """Activate or extend a subscription; returns the new expiry date (ISO).

    A renewal made before the current period ends extends from that
    period's end, not from today, so paying early never costs days.
    """
    today = date.today()
    with _connect() as conn:
        row = conn.execute(
            "SELECT expires_at FROM subscriptions WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        current_expiry = (
            date.fromisoformat(row[0]) if row and row[0] >= today.isoformat() else today
        )
        new_expiry = (current_expiry + timedelta(days=days)).isoformat()
        conn.execute(
            """
            INSERT INTO subscriptions (chat_id, plan, expires_at, expiry_notified)
            VALUES (?, ?, ?, 0)
            ON CONFLICT(chat_id) DO UPDATE SET plan = ?, expires_at = ?, expiry_notified = 0
            """,
            (chat_id, plan, new_expiry, plan, new_expiry),
        )
    return new_expiry


def get_subscription(chat_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT plan, expires_at FROM subscriptions WHERE chat_id = ?", (chat_id,)
        ).fetchone()
    if not row:
        return None
    plan, expires_at = row
    return {"plan": plan, "expires_at": expires_at, "active": expires_at >= date.today().isoformat()}


def add_watched_email(chat_id: int, email: str) -> bool:
    with _connect() as conn:
        try:
            conn.execute(
                "INSERT INTO watched_emails (chat_id, email) VALUES (?, ?)", (chat_id, email)
            )
            return True
        except sqlite3.IntegrityError:
            return False


def remove_watched_email(chat_id: int, email: str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM watched_emails WHERE chat_id = ? AND email = ?", (chat_id, email)
        )
    return cur.rowcount > 0


def list_watched_emails(chat_id: int) -> list[str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT email FROM watched_emails WHERE chat_id = ?", (chat_id,)
        ).fetchall()
    return [r[0] for r in rows]


def update_last_breaches(chat_id: int, email: str, breaches: list[str]) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE watched_emails SET last_breaches = ? WHERE chat_id = ? AND email = ?",
            (json.dumps(breaches), chat_id, email),
        )


def all_watches_with_subscriptions() -> list[tuple[int, str, str, bool, str, list[str]]]:
    """Yield (chat_id, plan, expires_at, expiry_notified, email, last_breaches) per watch."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT s.chat_id, s.plan, s.expires_at, s.expiry_notified, w.email, w.last_breaches
            FROM subscriptions s
            JOIN watched_emails w ON w.chat_id = s.chat_id
            """
        ).fetchall()
    return [(r[0], r[1], r[2], bool(r[3]), r[4], json.loads(r[5])) for r in rows]


def mark_expiry_notified(chat_id: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE subscriptions SET expiry_notified = 1 WHERE chat_id = ?", (chat_id,))


def delete_user_data(chat_id: int) -> None:
    """Erase everything stored for a chat: subscription and all watched emails."""
    with _connect() as conn:
        conn.execute("DELETE FROM watched_emails WHERE chat_id = ?", (chat_id,))
        conn.execute("DELETE FROM subscriptions WHERE chat_id = ?", (chat_id,))
