from telegram import InlineKeyboardButton, InlineKeyboardMarkup
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
