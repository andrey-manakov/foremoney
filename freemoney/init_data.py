from .database import Database
from .constants import ACCOUNT_TYPES, ACCOUNT_GROUPS


def seed(db: Database, user_id: int) -> None:
    """Initialize account types and groups for a user if not present."""
    for atype in ACCOUNT_TYPES:
        db.execute(
            "INSERT OR IGNORE INTO account_types (name) VALUES (?)",
            (atype,),
        )
    for atype, groups in ACCOUNT_GROUPS.items():
        type_row = db.fetchone(
            "SELECT id FROM account_types WHERE name=?",
            (atype,),
        )
        if not type_row:
            continue
        type_id = type_row["id"]
        for group in groups:
            exists = db.fetchone(
                "SELECT 1 FROM account_groups WHERE user_id=? AND type_id=? AND name=?",
                (user_id, type_id, group),
            )
            if not exists:
                db.execute(
                    """
                    INSERT INTO account_groups (user_id, type_id, name)
                    VALUES (?, ?, ?)
                    """,
                    (user_id, type_id, group),
                )
