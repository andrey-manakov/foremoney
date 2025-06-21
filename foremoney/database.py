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
        name TEXT NOT NULL,
        archived INTEGER DEFAULT 0,
        UNIQUE(user_id, type_id, name)
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
        # ensure archived column exists for account_groups in old databases
        info = cur.execute("PRAGMA table_info(account_groups)").fetchall()
        if not any(row[1] == "archived" for row in info):
            cur.execute("ALTER TABLE account_groups ADD COLUMN archived INTEGER DEFAULT 0")
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

    # ----- settings helpers -----

    def set_setting(self, user_id: int, key: str, value: str) -> None:
        exists = self.fetchone(
            "SELECT id FROM settings WHERE user_id=? AND key=?",
            (user_id, key),
        )
        if exists:
            self.execute(
                "UPDATE settings SET value=? WHERE user_id=? AND key=?",
                (value, user_id, key),
            )
        else:
            self.execute(
                "INSERT INTO settings (user_id, key, value) VALUES (?, ?, ?)",
                (user_id, key, value),
            )

    def get_setting(self, user_id: int, key: str) -> str | None:
        row = self.fetchone(
            "SELECT value FROM settings WHERE user_id=? AND key=?",
            (user_id, key),
        )
        return row["value"] if row else None

    # ----- account/group management -----

    def add_account_group(self, user_id: int, type_id: int, name: str) -> int:
        cur = self.execute(
            "INSERT INTO account_groups (user_id, type_id, name) VALUES (?, ?, ?)",
            (user_id, type_id, name),
        )
        return cur.lastrowid

    def update_account_group_name(self, user_id: int, group_id: int, name: str) -> None:
        self.execute(
            "UPDATE account_groups SET name=? WHERE user_id=? AND id=?",
            (name, user_id, group_id),
        )

    def archive_account_group(self, user_id: int, group_id: int) -> None:
        self.execute(
            "UPDATE account_groups SET archived=1 WHERE user_id=? AND id=?",
            (user_id, group_id),
        )

    def update_account_name(self, user_id: int, account_id: int, name: str) -> None:
        self.execute(
            "UPDATE accounts SET name=? WHERE user_id=? AND id=?",
            (name, user_id, account_id),
        )

    def archive_account(self, user_id: int, account_id: int) -> None:
        self.execute(
            "UPDATE accounts SET archived=1 WHERE user_id=? AND id=?",
            (user_id, account_id),
        )

    def all_accounts(self, user_id: int, include_archived: bool = False) -> Iterable[sqlite3.Row]:
        query = """
            SELECT a.id, a.name, g.name AS group_name
            FROM accounts a
            JOIN account_groups g ON a.group_id=g.id
            WHERE a.user_id=? {arch}
            ORDER BY g.name, a.name
        """.format(arch="" if include_archived else "AND a.archived=0")
        return self.fetchall(query, (user_id,))

    def account_balance(self, user_id: int, account_id: int) -> float:
        inc = self.fetchone(
            "SELECT COALESCE(SUM(amount),0) AS s FROM transactions WHERE user_id=? AND to_account=?",
            (user_id, account_id),
        )["s"]
        out = self.fetchone(
            "SELECT COALESCE(SUM(amount),0) AS s FROM transactions WHERE user_id=? AND from_account=?",
            (user_id, account_id),
        )["s"]
        return inc - out

    def accounts_balance(self, user_id: int, account_ids: Iterable[int]) -> float:
        total = 0.0
        for aid in account_ids:
            total += self.account_balance(user_id, aid)
        return total

    def correction_account(self, user_id: int) -> int:
        row = self.fetchone(
            """
            SELECT a.id FROM accounts a
            JOIN account_groups g ON a.group_id=g.id
            JOIN account_types t ON g.type_id=t.id
            WHERE a.user_id=? AND t.name='capital' AND g.name='Corrections' AND a.archived=0
            ORDER BY a.id LIMIT 1
            """,
            (user_id,),
        )
        if row:
            return row["id"]
        group = self.fetchone(
            """
            SELECT g.id FROM account_groups g
            JOIN account_types t ON g.type_id=t.id
            WHERE g.user_id=? AND t.name='capital' AND g.name='Corrections'
            """,
            (user_id,),
        )
        if not group:
            type_row = self.fetchone("SELECT id FROM account_types WHERE name='capital'")
            gid = self.add_account_group(user_id, type_row["id"], "Corrections")
        else:
            gid = group["id"]
        return self.add_account(user_id, gid, "Default")
