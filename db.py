import sqlite3
import hashlib
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "library.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def get_setting(key, default=None):
    conn = get_connection()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default

def init_db():
    conn = get_connection()
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())

    cur = conn.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        h = hashlib.sha256("admin".encode()).hexdigest()
        conn.execute("INSERT INTO users(login, password_hash, role) VALUES (?,?,?)",
                     ("admin", h, "администратор"))
        h2 = hashlib.sha256("1234".encode()).hexdigest()
        conn.execute("INSERT INTO users(login, password_hash, role) VALUES (?,?,?)",
                     ("lib1", h2, "библиотекарь"))

    cur = conn.execute("SELECT COUNT(*) FROM genres")
    if cur.fetchone()[0] == 0:
        conn.executemany("INSERT INTO genres(name) VALUES (?)",
                         [("Роман",), ("Фантастика",), ("Учебник",), ("Детектив",)])

    cur = conn.execute("SELECT COUNT(*) FROM categories")
    if cur.fetchone()[0] == 0:
        conn.executemany("INSERT INTO categories(name, loan_days) VALUES (?,?)",
                         [("Студент", 14), ("Преподаватель", 30), ("Школьник", 14)])

    # настройки штрафов и резерва
    defaults = {
        "fine_per_day": "10",
        "fine_max": "500",
        "reserve_days": "3",
    }
    for k, v in defaults.items():
        cur = conn.execute("SELECT COUNT(*) FROM settings WHERE key=?", (k,))
        if cur.fetchone()[0] == 0:
            conn.execute("INSERT INTO settings(key, value) VALUES (?,?)", (k, v))

    conn.commit()
    conn.close()

def check_login(login, password):
    h = hashlib.sha256(password.encode()).hexdigest()
    conn = get_connection()
    row = conn.execute("SELECT id, role FROM users WHERE login=? AND password_hash=?",
                       (login, h)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_setting(key, default=None):
    conn = get_connection()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default