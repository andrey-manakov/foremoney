from __future__ import annotations

from typing import Iterable, Mapping, Any


def make_labels(items: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return [{"id": id, "name": "name (value)"}, ...] for items with id,name,value."""
    return [
        {"id": item["id"], "name": f"{item['name']} ({item['value']})"}
        for item in items
    ]


def labels_map(labels: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """Map label name to original id."""
    return {lbl["name"]: lbl["id"] for lbl in labels}


def format_transaction(tx: Mapping[str, Any]) -> str:
    """Return short description of a transaction for inline buttons."""
    from ..constants import ACCOUNT_TYPE_CODES

    f_code = ACCOUNT_TYPE_CODES.get(tx["from_type"], "?")
    t_code = ACCOUNT_TYPE_CODES.get(tx["to_type"], "?")
    return (
        f"{f_code}-{tx['from_group']}-{tx['from_name']} "
        f"-{tx['amount']}-> "
        f"{t_code}-{tx['to_group']}-{tx['to_name']}"
    )
