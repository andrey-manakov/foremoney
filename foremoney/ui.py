from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from typing import Iterable, Mapping, Sequence


def items_keyboard(items: Iterable[Mapping], prefix: str, extra_buttons: Sequence[InlineKeyboardButton] | None = None) -> InlineKeyboardMarkup:
    """Create InlineKeyboardMarkup from DB rows.

    `items` should be an iterable of mappings with at least ``id`` and ``name`` keys.
    ``prefix`` is used to build ``callback_data`` as ``f"{prefix}:{id}"``.
    ``extra_buttons`` if provided is appended as separate rows.
    """
    buttons = [
        [InlineKeyboardButton(str(item["name"]), callback_data=f"{prefix}:{item['id']}")]
        for item in items
    ]
    if extra_buttons:
        for btn in extra_buttons:
            buttons.append([btn])
    return InlineKeyboardMarkup(buttons)


def items_reply_keyboard(
    items: Iterable[Mapping],
    extra_labels: Sequence[str] | None = None,
    columns: int = 1,
    extra_columns: int | None = None,
) -> ReplyKeyboardMarkup:
    """Create ReplyKeyboardMarkup from DB rows.

    ``items`` should be an iterable of mappings with at least ``name`` key.
    ``extra_labels`` if provided will be appended at the end.
    ``columns`` controls how many buttons are placed in a single row.
    ``extra_columns`` controls how many extra buttons are placed per row. If
    ``None`` they all appear on a single row for backwards compatibility.
    """
    buttons: list[list[KeyboardButton]] = []
    row: list[KeyboardButton] = []
    for idx, item in enumerate(items, 1):
        row.append(KeyboardButton(str(item["name"])))
        if idx % columns == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    if extra_labels:
        if extra_columns is None:
            buttons.append([KeyboardButton(lbl) for lbl in extra_labels])
        else:
            row = []
            for idx, lbl in enumerate(extra_labels, 1):
                row.append(KeyboardButton(lbl))
                if idx % extra_columns == 0:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
