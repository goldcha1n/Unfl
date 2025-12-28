import sqlite3
import hashlib

DB_NAME = "messenger.db"


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            contact_id INTEGER NOT NULL,
            UNIQUE(user_id, contact_id),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(contact_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(sender_id) REFERENCES users(id),
            FOREIGN KEY(receiver_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


def get_user_by_username(username: str):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()

    if row:
        return {"id": row["id"], "username": row["username"], "password": row["password"]}
    return None


def create_user(username: str, password: str):
    if get_user_by_username(username) is not None:
        return None

    pw_hash = hash_password(password)
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, pw_hash))
        conn.commit()
        user_id = c.lastrowid
    except sqlite3.IntegrityError:
        user_id = None
    conn.close()
    return user_id


def verify_user(username: str, password: str):
    user = get_user_by_username(username)
    if user is None:
        return None

    if user["password"] != hash_password(password):
        return None

    return {"id": user["id"], "username": user["username"]}


def add_contact(user_id: int, contact_username: str):
    contact_user = get_user_by_username(contact_username)
    if contact_user is None or contact_user["id"] == user_id:
        return False

    contact_id = contact_user["id"]
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("SELECT 1 FROM contacts WHERE user_id = ? AND contact_id = ?", (user_id, contact_id))
    if c.fetchone():
        conn.close()
        return False

    try:
        c.execute("INSERT INTO contacts (user_id, contact_id) VALUES (?, ?)", (user_id, contact_id))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return False

    conn.close()
    return True


def get_contacts(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT u.id as id, u.username as username
        FROM contacts c
        JOIN users u ON c.contact_id = u.id
        WHERE c.user_id = ?
        ORDER BY u.username
    """, (user_id,))

    rows = c.fetchall()
    conn.close()
    return [{"id": row["id"], "username": row["username"]} for row in rows]


def get_messages(user_id: int, contact_id: int):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT sender_id, receiver_id, content, timestamp
        FROM messages
        WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)
        ORDER BY timestamp
    """, (user_id, contact_id, contact_id, user_id))

    rows = c.fetchall()
    conn.close()

    return [{
        "sender_id": row["sender_id"],
        "receiver_id": row["receiver_id"],
        "content": row["content"],
        "timestamp": row["timestamp"]
    } for row in rows]


def add_message(sender_id: int, receiver_username: str, content: str):
    receiver = get_user_by_username(receiver_username)
    if receiver is None:
        return False

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT INTO messages (sender_id, receiver_id, content) VALUES (?, ?, ?)",
        (sender_id, receiver["id"], content)
    )
    conn.commit()
    conn.close()
    return True
