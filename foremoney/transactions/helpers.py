from __future__ import annotations

from typing import Iterable, Mapping, Any
from datetime import datetime


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
    """Return detailed description of a transaction."""
    from ..constants import ACCOUNT_TYPE_CODES

    data = dict(tx)

    f_code = ACCOUNT_TYPE_CODES.get(data["from_type"], "?")
    t_code = ACCOUNT_TYPE_CODES.get(data["to_type"], "?")

    ts = data.get("ts")
    if ts:
        try:
            ts = datetime.fromisoformat(str(ts)).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            ts = str(ts)
    else:
        ts = "N/A"

    return (
        f"from: {f_code} - {data['from_group']} - {data['from_name']}\n"
        f"to: {t_code} - {data['to_group']} - {data['to_name']}\n"
        f"amount: {data['amount']}\n"
        f"date: {ts}"
    )


def transaction_summary(tx: Mapping[str, Any]) -> str:
    """Return single-line summary of a transaction for list view."""
    data = dict(tx)
    return (
        f"{data['from_name']} "
        f"-> {data['amount']} -> "
        f"{data['to_name']}"
    )
