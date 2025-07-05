import sqlite3
from pathlib import Path
from typing import Iterable, Tuple
import secrets
import csv
from io import StringIO, BytesIO
from zipfile import ZipFile, ZIP_DEFLATED


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
    """
    CREATE TABLE IF NOT EXISTS user_family (
        user_id INTEGER PRIMARY KEY,
        family_id INTEGER NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS family_invites (
        token TEXT PRIMARY KEY,
        family_id INTEGER NOT NULL
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

    def family_id(self, user_id: int) -> int:
        row = self.fetchone(
            "SELECT family_id FROM user_family WHERE user_id=?",
            (user_id,),
        )
        return row["family_id"] if row else user_id

    def create_family_invite(self, family_id: int) -> str:
        token = secrets.token_urlsafe(8)
        self.execute(
            "INSERT INTO family_invites (token, family_id) VALUES (?, ?)",
            (token, family_id),
        )
        return token

    def use_family_invite(self, token: str, user_id: int) -> bool:
        row = self.fetchone(
            "SELECT family_id FROM family_invites WHERE token=?",
            (token,),
        )
        if not row:
            return False
        family_id = row["family_id"]
        self.execute("DELETE FROM family_invites WHERE token=?", (token,))
        self.execute(
            "INSERT OR REPLACE INTO user_family (user_id, family_id) VALUES (?, ?)",
            (user_id, family_id),
        )
        return True

    def account_types(self) -> Iterable[sqlite3.Row]:
        return self.fetchall("SELECT id, name FROM account_types ORDER BY name")

    def account_groups(self, user_id: int, type_id: int) -> Iterable[sqlite3.Row]:
        user_id = self.family_id(user_id)
        return self.fetchall(
            "SELECT id, name FROM account_groups WHERE user_id=? AND type_id=? ORDER BY name",
            (user_id, type_id),
        )

    def accounts(self, user_id: int, group_id: int) -> Iterable[sqlite3.Row]:
        user_id = self.family_id(user_id)
        return self.fetchall(
            """
            SELECT id, name FROM accounts
            WHERE user_id=? AND group_id=? AND archived=0
            ORDER BY name
            """,
            (user_id, group_id),
        )

    def add_account(self, user_id: int, group_id: int, name: str) -> int:
        user_id = self.family_id(user_id)
        cur = self.execute(
            "INSERT INTO accounts (user_id, group_id, name) VALUES (?, ?, ?)",
            (user_id, group_id, name),
        )
        return cur.lastrowid

    def add_transaction(
        self,
        user_id: int,
        from_id: int,
        to_id: int,
        amount: float,
        ts: str | None = None,
    ) -> int:
        user_id = self.family_id(user_id)
        if ts is not None:
            cur = self.execute(
                """
                INSERT INTO transactions (user_id, from_account, to_account, amount, ts)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, from_id, to_id, amount, ts),
            )
        else:
            cur = self.execute(
                """
                INSERT INTO transactions (user_id, from_account, to_account, amount)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, from_id, to_id, amount),
            )
        return cur.lastrowid

    def transactions(
        self,
        user_id: int,
        limit: int,
        offset: int,
        filters: dict | None = None,
    ) -> Iterable[sqlite3.Row]:
        """Return transactions list applying optional filters."""
        user_id = self.family_id(user_id)
        query = """
            SELECT t.id, t.amount, t.ts,
                   fa.name AS from_name, ta.name AS to_name,
                   fg.name AS from_group, tg.name AS to_group,
                   ft.name AS from_type, tt.name AS to_type
            FROM transactions t
            JOIN accounts fa ON fa.id=t.from_account
            JOIN account_groups fg ON fa.group_id=fg.id
            JOIN account_types ft ON fg.type_id=ft.id
            JOIN accounts ta ON ta.id=t.to_account
            JOIN account_groups tg ON ta.group_id=tg.id
            JOIN account_types tt ON tg.type_id=tt.id
            WHERE t.user_id=?
        """
        params: list = [user_id]
        if filters:
            if filters.get("min_date"):
                query += " AND date(t.ts) >= date(?)"
                params.append(filters["min_date"])
            if filters.get("max_date"):
                query += " AND date(t.ts) <= date(?)"
                params.append(filters["max_date"])
            if filters.get("min_amount") is not None:
                query += " AND t.amount >= ?"
                params.append(filters["min_amount"])
            if filters.get("max_amount") is not None:
                query += " AND t.amount <= ?"
                params.append(filters["max_amount"])
            if filters.get("group_id"):
                query += " AND (fg.id=? OR tg.id=?)"
                params.extend([filters["group_id"], filters["group_id"]])
            if filters.get("account_id"):
                query += " AND (fa.id=? OR ta.id=?)"
                params.extend([filters["account_id"], filters["account_id"]])
        query += " ORDER BY t.id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        return self.fetchall(query, params)

    def transaction(self, user_id: int, tx_id: int) -> sqlite3.Row | None:
        user_id = self.family_id(user_id)
        return self.fetchone(
            """
            SELECT t.id, t.amount, t.ts,
                   fa.name AS from_name, ta.name AS to_name,
                   fg.name AS from_group, tg.name AS to_group,
                   ft.name AS from_type, tt.name AS to_type
            FROM transactions t
            JOIN accounts fa ON fa.id=t.from_account
            JOIN account_groups fg ON fa.group_id=fg.id
            JOIN account_types ft ON fg.type_id=ft.id
            JOIN accounts ta ON ta.id=t.to_account
            JOIN account_groups tg ON ta.group_id=tg.id
            JOIN account_types tt ON tg.type_id=tt.id
            WHERE t.user_id=? AND t.id=?
            """,
            (user_id, tx_id),
        )

    def delete_transaction(self, user_id: int, tx_id: int) -> None:
        user_id = self.family_id(user_id)
        self.execute("DELETE FROM transactions WHERE user_id=? AND id=?", (user_id, tx_id))

    def update_transaction_amount(self, user_id: int, tx_id: int, amount: float) -> None:
        user_id = self.family_id(user_id)
        self.execute(
            "UPDATE transactions SET amount=? WHERE user_id=? AND id=?",
            (amount, user_id, tx_id),
        )

    # ----- settings helpers -----

    def set_setting(self, user_id: int, key: str, value: str) -> None:
        user_id = self.family_id(user_id)
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
        user_id = self.family_id(user_id)
        row = self.fetchone(
            "SELECT value FROM settings WHERE user_id=? AND key=?",
            (user_id, key),
        )
        return row["value"] if row else None

    # ----- account/group management -----

    def add_account_group(self, user_id: int, type_id: int, name: str) -> int:
        user_id = self.family_id(user_id)
        cur = self.execute(
            "INSERT INTO account_groups (user_id, type_id, name) VALUES (?, ?, ?)",
            (user_id, type_id, name),
        )
        return cur.lastrowid

    def update_account_group_name(self, user_id: int, group_id: int, name: str) -> None:
        user_id = self.family_id(user_id)
        self.execute(
            "UPDATE account_groups SET name=? WHERE user_id=? AND id=?",
            (name, user_id, group_id),
        )

    def archive_account_group(self, user_id: int, group_id: int) -> None:
        user_id = self.family_id(user_id)
        self.execute(
            "UPDATE account_groups SET archived=1 WHERE user_id=? AND id=?",
            (user_id, group_id),
        )

    def update_account_name(self, user_id: int, account_id: int, name: str) -> None:
        user_id = self.family_id(user_id)
        self.execute(
            "UPDATE accounts SET name=? WHERE user_id=? AND id=?",
            (name, user_id, account_id),
        )

    def archive_account(self, user_id: int, account_id: int) -> None:
        user_id = self.family_id(user_id)
        self.execute(
            "UPDATE accounts SET archived=1 WHERE user_id=? AND id=?",
            (user_id, account_id),
        )

    def all_accounts(self, user_id: int, include_archived: bool = False) -> Iterable[sqlite3.Row]:
        user_id = self.family_id(user_id)
        query = """
            SELECT a.id, a.name, g.name AS group_name
            FROM accounts a
            JOIN account_groups g ON a.group_id=g.id
            WHERE a.user_id=? {arch}
            ORDER BY g.name, a.name
        """.format(arch="" if include_archived else "AND a.archived=0")
        return self.fetchall(query, (user_id,))

    def account_balance(self, user_id: int, account_id: int) -> float:
        user_id = self.family_id(user_id)
        inc = self.fetchone(
            "SELECT COALESCE(SUM(amount),0) AS s FROM transactions WHERE user_id=? AND to_account=?",
            (user_id, account_id),
        )["s"]
        out = self.fetchone(
            "SELECT COALESCE(SUM(amount),0) AS s FROM transactions WHERE user_id=? AND from_account=?",
            (user_id, account_id),
        )["s"]
        return inc - out

    def account_value(self, user_id: int, account_id: int) -> float:
        """Return account value based on its type."""
        user_id = self.family_id(user_id)
        bal = self.account_balance(user_id, account_id)
        row = self.fetchone(
            """
            SELECT t.name AS type_name
            FROM accounts a
            JOIN account_groups g ON a.group_id=g.id
            JOIN account_types t ON g.type_id=t.id
            WHERE a.user_id=? AND a.id=?
            """,
            (user_id, account_id),
        )
        if row and row["type_name"] in ("liabilities", "income", "capital"):
            return -bal
        return bal

    def accounts_with_value(self, user_id: int, group_id: int):
        """Return accounts list with calculated values."""
        user_id = self.family_id(user_id)
        accs = self.accounts(user_id, group_id)
        result = []
        for a in accs:
            val = self.account_value(user_id, a["id"])
            result.append({"id": a["id"], "name": a["name"], "value": val})
        return result

    def account_group_value(self, user_id: int, group_id: int) -> float:
        """Return total value of all accounts within a group."""
        user_id = self.family_id(user_id)
        total = 0.0
        for acc in self.accounts(user_id, group_id):
            total += self.account_value(user_id, acc["id"])
        return total

    def account_groups_with_value(self, user_id: int, type_id: int):
        """Return account groups list with calculated values."""
        user_id = self.family_id(user_id)
        groups = self.account_groups(user_id, type_id)
        result = []
        for g in groups:
            val = self.account_group_value(user_id, g["id"])
            result.append({"id": g["id"], "name": g["name"], "value": val})
        return result

    def account_type_value(self, user_id: int, type_id: int) -> float:
        """Return total value of all accounts within a type."""
        user_id = self.family_id(user_id)
        total = 0.0
        for g in self.account_groups(user_id, type_id):
            total += self.account_group_value(user_id, g["id"])
        return total

    def account_types_with_value(self, user_id: int):
        """Return account types list with calculated values."""
        user_id = self.family_id(user_id)
        types = self.account_types()
        result = []
        for t in types:
            val = self.account_type_value(user_id, t["id"])
            result.append({"id": t["id"], "name": t["name"], "value": val})
        return result

    def accounts_balance(self, user_id: int, account_ids: Iterable[int]) -> float:
        user_id = self.family_id(user_id)
        total = 0.0
        for aid in account_ids:
            total += self.account_balance(user_id, aid)
        return total

    def correction_account(self, user_id: int) -> int:
        user_id = self.family_id(user_id)
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

    def account_type_transactions(self, user_id: int, type_id: int):
        """Return transactions affecting given account type ordered by time."""
        user_id = self.family_id(user_id)
        return self.fetchall(
            """
            SELECT t.ts, t.amount,
                   ftype.name AS from_type, ttype.name AS to_type,
                   ftype.id AS from_type_id, ttype.id AS to_type_id
            FROM transactions t
            JOIN accounts fa ON fa.id=t.from_account
            JOIN account_groups fg ON fa.group_id=fg.id
            JOIN account_types ftype ON fg.type_id=ftype.id
            JOIN accounts ta ON ta.id=t.to_account
            JOIN account_groups tg ON ta.group_id=tg.id
            JOIN account_types ttype ON tg.type_id=ttype.id
            WHERE t.user_id=? AND (ftype.id=? OR ttype.id=?)
            ORDER BY t.ts, t.id
            """,
            (user_id, type_id, type_id),
        )

    def account_group_transactions(self, user_id: int, group_id: int):
        """Return transactions affecting given account group ordered by time."""
        user_id = self.family_id(user_id)
        return self.fetchall(
            """
            SELECT t.ts, t.amount,
                   ftype.name AS from_type, ttype.name AS to_type,
                   fg.id AS from_group_id, tg.id AS to_group_id
            FROM transactions t
            JOIN accounts fa ON fa.id=t.from_account
            JOIN account_groups fg ON fa.group_id=fg.id
            JOIN account_types ftype ON fg.type_id=ftype.id
            JOIN accounts ta ON ta.id=t.to_account
            JOIN account_groups tg ON ta.group_id=tg.id
            JOIN account_types ttype ON tg.type_id=ttype.id
            WHERE t.user_id=? AND (fg.id=? OR tg.id=?)
            ORDER BY t.ts, t.id
            """,
            (user_id, group_id, group_id),
        )


def export_archive(db_path: Path) -> bytes:
    """Return a ZIP archive with CSV files of all DB tables."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    tables = [row[0] for row in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )]
    buf = BytesIO()
    with ZipFile(buf, "w", compression=ZIP_DEFLATED) as zf:
        for table in tables:
            rows = cur.execute(f"SELECT * FROM {table}").fetchall()
            cols = [d[0] for d in cur.description]
            s_buf = StringIO()
            writer = csv.writer(s_buf)
            writer.writerow(cols)
            writer.writerows(rows)
            zf.writestr(f"{table}.csv", s_buf.getvalue())
    conn.close()
    buf.seek(0)
    return buf.getvalue()


def import_archive(db_path: Path, data: bytes) -> None:
    """Replace DB with tables provided in the ZIP archive."""
    if db_path.exists():
        db_path.unlink()
    db = Database(db_path)  # create schema
    db.conn.close()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    with ZipFile(BytesIO(data)) as zf:
        for name in zf.namelist():
            if not name.endswith(".csv"):
                continue
            table = Path(name).stem
            content = zf.read(name).decode()
            reader = csv.reader(StringIO(content))
            rows = list(reader)
            if not rows:
                continue
            header = rows[0]
            placeholders = ",".join("?" * len(header))
            for row in rows[1:]:
                cur.execute(
                    f"INSERT INTO {table} ({','.join(header)}) VALUES ({placeholders})",
                    row,
                )
    conn.commit()
    conn.close()

