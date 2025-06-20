import sqlite3
from pathlib import Path
from typing import Iterable, Tuple


SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS account_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS account_groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        type_id INTEGER NOT NULL REFERENCES account_types(id),
        name TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        group_id INTEGER NOT NULL REFERENCES account_groups(id),
        name TEXT NOT NULL,
        archived INTEGER DEFAULT 0
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        from_account INTEGER NOT NULL REFERENCES accounts(id),
        to_account INTEGER NOT NULL REFERENCES accounts(id),
        amount REAL NOT NULL,
        ts DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        key TEXT NOT NULL,
        value TEXT
    );
    """,
]


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        cur = self.conn.cursor()
        for stmt in SCHEMA:
            cur.execute(stmt)
        self.conn.commit()

    def execute(self, query: str, params: Iterable = ()):  # simple wrapper
        cur = self.conn.execute(query, params)
        self.conn.commit()
        return cur

    def fetchall(self, query: str, params: Iterable = ()) -> Iterable[sqlite3.Row]:
        cur = self.conn.execute(query, params)
        return cur.fetchall()

    def fetchone(self, query: str, params: Iterable = ()) -> sqlite3.Row | None:
        cur = self.conn.execute(query, params)
        return cur.fetchone()
