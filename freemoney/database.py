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

    # ---- high level helpers ----

    def account_types(self) -> Iterable[sqlite3.Row]:
        return self.fetchall("SELECT id, name FROM account_types ORDER BY name")

    def account_groups(self, user_id: int, type_id: int) -> Iterable[sqlite3.Row]:
        return self.fetchall(
            "SELECT id, name FROM account_groups WHERE user_id=? AND type_id=? ORDER BY name",
            (user_id, type_id),
        )

    def accounts(self, user_id: int, group_id: int) -> Iterable[sqlite3.Row]:
        return self.fetchall(
            """
            SELECT id, name FROM accounts
            WHERE user_id=? AND group_id=? AND archived=0
            ORDER BY name
            """,
            (user_id, group_id),
        )

    def add_account(self, user_id: int, group_id: int, name: str) -> int:
        cur = self.execute(
            "INSERT INTO accounts (user_id, group_id, name) VALUES (?, ?, ?)",
            (user_id, group_id, name),
        )
        return cur.lastrowid

    def add_transaction(self, user_id: int, from_id: int, to_id: int, amount: float) -> int:
        cur = self.execute(
            """
            INSERT INTO transactions (user_id, from_account, to_account, amount)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, from_id, to_id, amount),
        )
        return cur.lastrowid

    def transactions(self, user_id: int, limit: int, offset: int) -> Iterable[sqlite3.Row]:
        return self.fetchall(
            """
            SELECT t.id, t.amount, t.ts,
                   fa.name AS from_name, ta.name AS to_name
            FROM transactions t
            JOIN accounts fa ON fa.id=t.from_account
            JOIN accounts ta ON ta.id=t.to_account
            WHERE t.user_id=?
            ORDER BY t.id DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset),
        )

    def transaction(self, user_id: int, tx_id: int) -> sqlite3.Row | None:
        return self.fetchone(
            """
            SELECT t.id, t.amount, t.ts,
                   fa.name AS from_name, ta.name AS to_name
            FROM transactions t
            JOIN accounts fa ON fa.id=t.from_account
            JOIN accounts ta ON ta.id=t.to_account
            WHERE t.user_id=? AND t.id=?
            """,
            (user_id, tx_id),
        )

    def delete_transaction(self, user_id: int, tx_id: int) -> None:
        self.execute("DELETE FROM transactions WHERE user_id=? AND id=?", (user_id, tx_id))

    def update_transaction_amount(self, user_id: int, tx_id: int, amount: float) -> None:
        self.execute(
            "UPDATE transactions SET amount=? WHERE user_id=? AND id=?",
            (amount, user_id, tx_id),
        )
