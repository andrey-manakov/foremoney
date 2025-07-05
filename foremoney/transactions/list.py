from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import ContextTypes, ConversationHandler

from .helpers import format_transaction, transaction_summary
from ..ui import items_reply_keyboard

from ..states import (
    TX_LIST,
    TX_DETAILS,
    TX_EDIT_AMOUNT,
    TX_FILTER_MIN_DATE,
    TX_FILTER_MAX_DATE,
    TX_FILTER_MIN_AMOUNT,
    TX_FILTER_MAX_AMOUNT,
    TX_FILTER_ACC_TYPE,
    TX_FILTER_GROUP,
    TX_FILTER_ACCOUNT,
)

class TransactionListMixin:
    """Handlers for listing and editing transactions."""

    async def start_transactions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data["tx_filters"] = {}
        context.user_data["tx_offset"] = 0
        return await self._send_transactions(update.message, update.effective_user.id, 0, context)

    async def _send_transactions(
        self, sender, user_id: int, offset: int, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        msg_obj = sender if hasattr(sender, "reply_text") else sender.message
        filters = context.user_data.get("tx_filters", {})
        txs = self.db.transactions(user_id, 10, offset, filters)
        buttons = [
            [
                InlineKeyboardButton(
                    transaction_summary(tx), callback_data=f"tx:{tx['id']}"
                )
            ]
            for tx in txs
        ]
        if txs:
            buttons.append([InlineKeyboardButton("Next", callback_data="next")])
        await msg_obj.reply_text(
            "Transactions:",
            reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
        )
        await msg_obj.reply_text(
            "Filters:", reply_markup=self._filter_menu_keyboard()
        )
        return TX_LIST

    async def tx_filter_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        if text == "Transactions":
            return await self.start_transactions(update, context)
        if text == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        if text == "Reset filter":
            context.user_data["tx_filters"] = {}
            context.user_data["tx_offset"] = 0
            await update.message.reply_text("Filters reset")
            return await self._send_transactions(update.message, update.effective_user.id, 0, context)
        if text == "Min date":
            await update.message.reply_text("Enter min date YYYY-MM-DD")
            return TX_FILTER_MIN_DATE
        if text == "Max date":
            await update.message.reply_text("Enter max date YYYY-MM-DD")
            return TX_FILTER_MAX_DATE
        if text == "Min amount":
            await update.message.reply_text("Enter minimum amount")
            return TX_FILTER_MIN_AMOUNT
        if text == "Max amount":
            await update.message.reply_text("Enter maximum amount")
            return TX_FILTER_MAX_AMOUNT
        if text == "Account group":
            types = self.db.account_types()
            type_labels = [{"id": t["id"], "name": t["name"]} for t in types]
            context.user_data["tx_type_map"] = {t["name"]: t["id"] for t in types}
            context.user_data["filter_step"] = "group"
            await update.message.reply_text(
                "Select account type",
                reply_markup=items_reply_keyboard(type_labels, ["Cancel"], columns=2),
            )
            return TX_FILTER_ACC_TYPE
        if text == "Account":
            types = self.db.account_types()
            type_labels = [{"id": t["id"], "name": t["name"]} for t in types]
            context.user_data["tx_type_map"] = {t["name"]: t["id"] for t in types}
            context.user_data["filter_step"] = "account"
            await update.message.reply_text(
                "Select account type",
                reply_markup=items_reply_keyboard(type_labels, ["Cancel"], columns=2),
            )
            return TX_FILTER_ACC_TYPE
        await update.message.reply_text("Use menu")
        return TX_LIST

    async def tx_filter_min_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text.strip()
        if text == "Cancel":
            return await self._send_transactions(update.message, update.effective_user.id, 0, context)
        try:
            datetime.fromisoformat(text)
            context.user_data.setdefault("tx_filters", {})["min_date"] = text
        except ValueError:
            await update.message.reply_text("Invalid date format")
            return TX_FILTER_MIN_DATE
        context.user_data["tx_offset"] = 0
        return await self._send_transactions(update.message, update.effective_user.id, 0, context)

    async def tx_filter_max_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text.strip()
        if text == "Cancel":
            return await self._send_transactions(update.message, update.effective_user.id, 0, context)
        try:
            datetime.fromisoformat(text)
            context.user_data.setdefault("tx_filters", {})["max_date"] = text
        except ValueError:
            await update.message.reply_text("Invalid date format")
            return TX_FILTER_MAX_DATE
        context.user_data["tx_offset"] = 0
        return await self._send_transactions(update.message, update.effective_user.id, 0, context)

    async def tx_filter_min_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text.strip()
        if text == "Cancel":
            return await self._send_transactions(update.message, update.effective_user.id, 0, context)
        try:
            val = float(text)
            context.user_data.setdefault("tx_filters", {})["min_amount"] = val
        except ValueError:
            await update.message.reply_text("Please enter a number")
            return TX_FILTER_MIN_AMOUNT
        context.user_data["tx_offset"] = 0
        return await self._send_transactions(update.message, update.effective_user.id, 0, context)

    async def tx_filter_max_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text.strip()
        if text == "Cancel":
            return await self._send_transactions(update.message, update.effective_user.id, 0, context)
        try:
            val = float(text)
            context.user_data.setdefault("tx_filters", {})["max_amount"] = val
        except ValueError:
            await update.message.reply_text("Please enter a number")
            return TX_FILTER_MAX_AMOUNT
        context.user_data["tx_offset"] = 0
        return await self._send_transactions(update.message, update.effective_user.id, 0, context)

    async def tx_filter_acc_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        if text == "Cancel":
            return await self._send_transactions(update.message, update.effective_user.id, 0, context)
        type_map = context.user_data.get("tx_type_map", {})
        if text not in type_map:
            await update.message.reply_text("Use provided buttons")
            return TX_FILTER_ACC_TYPE
        type_id = type_map[text]
        context.user_data["selected_type"] = type_id
        groups = self.db.account_groups(update.effective_user.id, type_id)
        labels = [{"id": g["id"], "name": g["name"]} for g in groups]
        context.user_data["tx_group_map"] = {g["name"]: g["id"] for g in labels}
        await update.message.reply_text(
            "Select group",
            reply_markup=items_reply_keyboard(labels, ["Back", "Cancel"], columns=2),
        )
        return TX_FILTER_GROUP

    async def tx_filter_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        if text == "Cancel":
            return await self._send_transactions(update.message, update.effective_user.id, 0, context)
        if text == "Back":
            types = self.db.account_types()
            type_labels = [{"id": t["id"], "name": t["name"]} for t in types]
            context.user_data["tx_type_map"] = {t["name"]: t["id"] for t in types}
            await update.message.reply_text(
                "Select account type",
                reply_markup=items_reply_keyboard(type_labels, ["Cancel"], columns=2),
            )
            return TX_FILTER_ACC_TYPE
        group_map = context.user_data.get("tx_group_map", {})
        if text not in group_map:
            await update.message.reply_text("Use provided buttons")
            return TX_FILTER_GROUP
        gid = group_map[text]
        if context.user_data.get("filter_step") == "group":
            context.user_data.setdefault("tx_filters", {})["group_id"] = gid
            context.user_data["tx_offset"] = 0
            return await self._send_transactions(update.message, update.effective_user.id, 0, context)
        context.user_data["selected_group"] = gid
        accounts = self.db.accounts(update.effective_user.id, gid)
        labels = [{"id": a["id"], "name": a["name"]} for a in accounts]
        context.user_data["tx_account_map"] = {a["name"]: a["id"] for a in labels}
        await update.message.reply_text(
            "Select account",
            reply_markup=items_reply_keyboard(labels, ["Back", "Cancel"], columns=2),
        )
        return TX_FILTER_ACCOUNT

    async def tx_filter_account(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        if text == "Cancel":
            return await self._send_transactions(update.message, update.effective_user.id, 0, context)
        if text == "Back":
            gid = context.user_data.get("selected_group")
            accounts = self.db.accounts(update.effective_user.id, gid)
            labels = [{"id": a["id"], "name": a["name"]} for a in accounts]
            context.user_data["tx_account_map"] = {a["name"]: a["id"] for a in labels}
            await update.message.reply_text(
                "Select account",
                reply_markup=items_reply_keyboard(labels, ["Back", "Cancel"], columns=2),
            )
            return TX_FILTER_ACCOUNT
        account_map = context.user_data.get("tx_account_map", {})
        if text not in account_map:
            await update.message.reply_text("Use provided buttons")
            return TX_FILTER_ACCOUNT
        aid = account_map[text]
        context.user_data.setdefault("tx_filters", {})["account_id"] = aid
        context.user_data["tx_offset"] = 0
        return await self._send_transactions(update.message, update.effective_user.id, 0, context)

    def _filter_menu_keyboard(self) -> ReplyKeyboardMarkup:
        buttons = [
            [KeyboardButton("Min date"), KeyboardButton("Max date")],
            [KeyboardButton("Min amount"), KeyboardButton("Max amount")],
            [KeyboardButton("Account group"), KeyboardButton("Account")],
            [KeyboardButton("Reset filter"), KeyboardButton("Cancel")],
        ]
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    async def tx_list_actions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        if query.data == "next":
            offset = context.user_data.get("tx_offset", 0) + 10
            context.user_data["tx_offset"] = offset
            await query.message.delete()
            return await self._send_transactions(query.message, user_id, offset, context)
        if query.data.startswith("tx:"):
            tx_id = int(query.data.split(":")[1])
            tx = self.db.transaction(user_id, tx_id)
            if not tx:
                await query.message.reply_text("Transaction not found")
                return TX_LIST
            context.user_data["tx_id"] = tx_id
            await query.message.reply_text(
                format_transaction(tx),
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("Edit", callback_data="edit")],
                        [InlineKeyboardButton("Delete", callback_data="delete")],
                    ]
                ),
            )
            return TX_DETAILS
        return TX_LIST

    async def tx_details_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        tx_id = context.user_data.get("tx_id")
        if query.data == "delete" and tx_id:
            self.db.delete_transaction(user_id, tx_id)
            await query.message.reply_text("Transaction deleted")
            return ConversationHandler.END
        if query.data == "edit" and tx_id:
            context.user_data["editing_tx"] = True
            await query.message.reply_text("Enter new amount")
            return TX_EDIT_AMOUNT
        return TX_DETAILS

    async def tx_edit_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            amount = float(update.message.text)
        except ValueError:
            await update.message.reply_text("Please enter a number")
            return TX_EDIT_AMOUNT
        user_id = update.effective_user.id
        tx_id = context.user_data.get("tx_id")
        if tx_id:
            self.db.update_transaction_amount(user_id, tx_id, amount)
            tx = self.db.transaction(user_id, tx_id)
            await update.message.reply_text(
                format_transaction(tx),
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("Edit", callback_data="edit")],
                        [InlineKeyboardButton("Delete", callback_data="delete")],
                    ]
                ),
            )
            return TX_DETAILS
        return ConversationHandler.END
