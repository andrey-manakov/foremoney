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
) -> ReplyKeyboardMarkup:
    """Create ReplyKeyboardMarkup from DB rows.

    ``items`` should be an iterable of mappings with at least ``name`` key.
    ``extra_labels`` if provided will be appended as last row of buttons.
    """
    buttons = [[KeyboardButton(str(item["name"]))] for item in items]
    if extra_labels:
        buttons.append([KeyboardButton(lbl) for lbl in extra_labels])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
