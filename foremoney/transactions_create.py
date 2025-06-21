from telegram import Update, InlineKeyboardButton
from telegram.ext import ContextTypes

from .ui import items_keyboard
from .states import (
    FROM_TYPE, FROM_GROUP, FROM_ACCOUNT,
    TO_TYPE, TO_GROUP, TO_ACCOUNT,
    AMOUNT, SUMMARY, ADD_ACCOUNT_NAME,
)

class TransactionCreateMixin:
    """Flow for creating a transaction."""

    async def start_create_transaction(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        types = self.db.account_types()
        await update.message.reply_text(
            "Select source account type",
            reply_markup=items_keyboard(types, "ftype"),
        )
        return FROM_TYPE

    async def from_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        type_id = int(query.data.split(":")[1])
        context.user_data["from_type"] = type_id
        groups = self.db.account_groups(update.effective_user.id, type_id)
        await query.message.reply_text(
            "Select source account group",
            reply_markup=items_keyboard(groups, "fgroup"),
        )
        return FROM_GROUP

    async def from_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        group_id = int(query.data.split(":")[1])
        context.user_data["from_group"] = group_id
        accounts = self.db.accounts(update.effective_user.id, group_id)
        extra = [InlineKeyboardButton("+", callback_data=f"addacc:from:{group_id}")]
        await query.message.reply_text(
            "Select source account",
            reply_markup=items_keyboard(accounts, "facc", extra_buttons=extra),
        )
        return FROM_ACCOUNT

    async def add_account_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        _, prefix, gid = query.data.split(":")
        context.user_data["add_prefix"] = prefix
        context.user_data["add_group"] = int(gid)
        await query.message.reply_text("Enter account name")
        return ADD_ACCOUNT_NAME

    async def add_account_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        name = update.message.text.strip()
        gid = context.user_data["add_group"]
        prefix = context.user_data["add_prefix"]
        user_id = update.effective_user.id
        self.db.add_account(user_id, gid, name)
        accounts = self.db.accounts(user_id, gid)
        extra = [InlineKeyboardButton("+", callback_data=f"addacc:{prefix}:{gid}")]
        await update.message.reply_text(
            "Select account",
            reply_markup=items_keyboard(
                accounts,
                "facc" if prefix == "from" else "tacc",
                extra_buttons=extra,
            ),
        )
        return FROM_ACCOUNT if prefix == "from" else TO_ACCOUNT

    async def from_account(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        account_id = int(query.data.split(":")[1])
        context.user_data["from_account"] = account_id
        types = self.db.account_types()
        await query.message.reply_text(
            "Select destination account type",
            reply_markup=items_keyboard(types, "ttype"),
        )
        return TO_TYPE

    async def to_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        type_id = int(query.data.split(":")[1])
        context.user_data["to_type"] = type_id
        groups = self.db.account_groups(update.effective_user.id, type_id)
        await query.message.reply_text(
            "Select destination account group",
            reply_markup=items_keyboard(groups, "tgroup"),
        )
        return TO_GROUP

    async def to_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        group_id = int(query.data.split(":")[1])
        context.user_data["to_group"] = group_id
        accounts = self.db.accounts(update.effective_user.id, group_id)
        extra = [InlineKeyboardButton("+", callback_data=f"addacc:to:{group_id}")]
        await query.message.reply_text(
            "Select destination account",
            reply_markup=items_keyboard(accounts, "tacc", extra_buttons=extra),
        )
        return TO_ACCOUNT

    async def to_account(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        account_id = int(query.data.split(":")[1])
        context.user_data["to_account"] = account_id
        await query.message.reply_text("Enter amount")
        context.user_data.pop("editing", None)
        return AMOUNT

    async def amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            amount = float(update.message.text)
        except ValueError:
            await update.message.reply_text("Please enter a number")
            return AMOUNT
        user_id = update.effective_user.id
        if context.user_data.get("editing"):
            tx_id = context.user_data["tx_id"]
            self.db.update_transaction_amount(user_id, tx_id, amount)
        else:
            tx_id = self.db.add_transaction(
                user_id,
                context.user_data["from_account"],
                context.user_data["to_account"],
                amount,
            )
            context.user_data["tx_id"] = tx_id
        tx = self.db.transaction(user_id, tx_id)
        await update.message.reply_text(
            f"{tx['from_name']} - {tx['amount']} -> {tx['to_name']}",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("Edit", callback_data="edit")],
                    [InlineKeyboardButton("Delete", callback_data="delete")],
                ]
            ),
        )
        return SUMMARY

