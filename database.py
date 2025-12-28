# database.py
import os
import sqlite3
import hashlib
from typing import Optional, Dict, List, Any

DB_PATH = os.getenv("DB_PATH", "app.db")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def init_db() -> None:
    conn = _conn()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                contact_id INTEGER NOT NULL,
                UNIQUE(user_id, contact_id),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(contact_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY(sender_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(receiver_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        conn.commit()
    finally:
        conn.close()


def create_user(username: str, password: str) -> Optional[int]:
    username = (username or "").strip()
    if not username:
        return None
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users(username, password_hash) VALUES (?, ?)",
            (username, _hash_password(password or "")),
        )
        conn.commit()
        return int(cur.lastrowid)
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    username = (username or "").strip()
    if not username:
        return None
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, username FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row["id"], "username": row["username"]}
    finally:
        conn.close()


def verify_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    username = (username or "").strip()
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        )
        row = cur.fetchone()
        if not row:
            return None
        if row["password_hash"] != _hash_password(password or ""):
            return None
        return {"id": row["id"], "username": row["username"]}
    finally:
        conn.close()


def add_contact(user_id: int, contact_username: str) -> bool:
    target = get_user_by_username(contact_username)
    if not target:
        return False
    if int(target["id"]) == int(user_id):
        return False

    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO contacts(user_id, contact_id) VALUES (?, ?)",
            (user_id, target["id"]),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_contacts(user_id: int) -> List[Dict[str, Any]]:
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT u.id, u.username
            FROM contacts c
            JOIN users u ON u.id = c.contact_id
            WHERE c.user_id = ?
            ORDER BY u.username COLLATE NOCASE ASC
            """,
            (user_id,),
        )
        rows = cur.fetchall()
        return [{"id": r["id"], "username": r["username"]} for r in rows]
    finally:
        conn.close()


def add_message(sender_id: int, receiver_username: str, content: str) -> bool:
    receiver = get_user_by_username(receiver_username)
    if not receiver:
        return False
    text = (content or "").strip()
    if not text:
        return False

    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO messages(sender_id, receiver_id, content)
            VALUES (?, ?, ?)
            """,
            (sender_id, receiver["id"], text),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_messages(user_id: int, other_id: int, limit: int = 200) -> List[Dict[str, Any]]:
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, sender_id, receiver_id, content, timestamp
            FROM messages
            WHERE (
              (sender_id = ? AND receiver_id = ?) OR
              (sender_id = ? AND receiver_id = ?)
            )
            ORDER BY id ASC
            LIMIT ?
            """,
            (user_id, other_id, other_id, user_id, limit),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r["id"],
                "sender_id": r["sender_id"],
                "receiver_id": r["receiver_id"],
                "content": r["content"],
                "timestamp": str(r["timestamp"]),
            }
            for r in rows
        ]
    finally:
        conn.close()


def get_messages_since(user_id: int, other_id: int, after_id: int, limit: int = 200) -> List[Dict[str, Any]]:
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, sender_id, receiver_id, content, timestamp
            FROM messages
            WHERE (
              (sender_id = ? AND receiver_id = ?) OR
              (sender_id = ? AND receiver_id = ?)
            )
            AND id > ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (user_id, other_id, other_id, user_id, after_id, limit),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r["id"],
                "sender_id": r["sender_id"],
                "receiver_id": r["receiver_id"],
                "content": r["content"],
                "timestamp": str(r["timestamp"]),
            }
            for r in rows
        ]
    finally:
        conn.close()
