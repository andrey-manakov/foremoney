from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import ContextTypes, ConversationHandler

from .ui import items_reply_keyboard
from .states import (
    FROM_TYPE,
    FROM_GROUP,
    FROM_ACCOUNT,
    TO_TYPE,
    TO_GROUP,
    TO_ACCOUNT,
    AMOUNT,
    ADD_ACCOUNT_NAME,
)

class TransactionCreateMixin:
    """Flow for creating a transaction."""

    async def start_create_transaction(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        types = self.db.account_types()
        context.user_data["from_type_map"] = {t["name"]: t["id"] for t in types}
        await update.message.reply_text(
            "Select source account type",
            reply_markup=items_reply_keyboard(types, ["Cancel"], columns=2),
        )
        return FROM_TYPE

    async def from_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        if text == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        type_map = context.user_data.get("from_type_map", {})
        if text not in type_map:
            await update.message.reply_text("Use provided buttons")
            return FROM_TYPE
        type_id = type_map[text]
        context.user_data["from_type"] = type_id
        groups = self.db.account_groups(update.effective_user.id, type_id)
        context.user_data["from_group_map"] = {g["name"]: g["id"] for g in groups}
        await update.message.reply_text(
            "Select source account group",
            reply_markup=items_reply_keyboard(groups, ["Back", "Cancel"], columns=2),
        )
        return FROM_GROUP

    async def from_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        if text == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        if text == "Back":
            return await self.start_create_transaction(update, context)
        group_map = context.user_data.get("from_group_map", {})
        if text not in group_map:
            await update.message.reply_text("Use provided buttons")
            return FROM_GROUP
        group_id = group_map[text]
        context.user_data["from_group"] = group_id
        accounts = self.db.accounts(update.effective_user.id, group_id)
        context.user_data["from_account_map"] = {a["name"]: a["id"] for a in accounts}
        context.user_data["account_prefix"] = "from"
        await update.message.reply_text(
            "Select source account",
            reply_markup=items_reply_keyboard(accounts, ["+ account", "Back", "Cancel"], columns=2),
        )
        return FROM_ACCOUNT


    async def add_account_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text.strip()
        gid = context.user_data["add_group"]
        prefix = context.user_data["add_prefix"]
        user_id = update.effective_user.id
        if text == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        if text == "Back":
            accounts = self.db.accounts(user_id, gid)
            acc_map_key = "from_account_map" if prefix == "from" else "to_account_map"
            context.user_data[acc_map_key] = {a["name"]: a["id"] for a in accounts}
            context.user_data["account_prefix"] = prefix
            await update.message.reply_text(
                "Select account",
                reply_markup=items_reply_keyboard(accounts, ["+ account", "Back", "Cancel"], columns=2),
            )
            return FROM_ACCOUNT if prefix == "from" else TO_ACCOUNT
        name = text
        self.db.add_account(user_id, gid, name)
        accounts = self.db.accounts(user_id, gid)
        acc_map_key = "from_account_map" if prefix == "from" else "to_account_map"
        context.user_data[acc_map_key] = {a["name"]: a["id"] for a in accounts}
        context.user_data["account_prefix"] = prefix
        await update.message.reply_text(
            "Select account",
            reply_markup=items_reply_keyboard(accounts, ["+ account", "Back", "Cancel"], columns=2),
        )
        return FROM_ACCOUNT if prefix == "from" else TO_ACCOUNT

    async def from_account(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        if text == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        if text == "Back":
            groups = self.db.account_groups(
                update.effective_user.id, context.user_data["from_type"]
            )
            context.user_data["from_group_map"] = {g["name"]: g["id"] for g in groups}
            await update.message.reply_text(
                "Select source account group",
                reply_markup=items_reply_keyboard(groups, ["Back", "Cancel"], columns=2),
            )
            return FROM_GROUP
        if text == "+ account":
            context.user_data["add_prefix"] = context.user_data.get("account_prefix")
            context.user_data["add_group"] = context.user_data["from_group"]
            await update.message.reply_text("Enter account name", reply_markup=ReplyKeyboardRemove())
            return ADD_ACCOUNT_NAME
        acc_map = context.user_data.get("from_account_map", {})
        if text not in acc_map:
            await update.message.reply_text("Use provided buttons")
            return FROM_ACCOUNT
        account_id = acc_map[text]
        context.user_data["from_account"] = account_id
        types = self.db.account_types()
        context.user_data["to_type_map"] = {t["name"]: t["id"] for t in types}
        await update.message.reply_text(
            "Select destination account type",
            reply_markup=items_reply_keyboard(types, ["Back", "Cancel"], columns=2),
        )
        return TO_TYPE

    async def to_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        if text == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        if text == "Back":
            accounts = self.db.accounts(
                update.effective_user.id, context.user_data["from_group"]
            )
            context.user_data["from_account_map"] = {a["name"]: a["id"] for a in accounts}
            context.user_data["account_prefix"] = "from"
            await update.message.reply_text(
                "Select source account",
                reply_markup=items_reply_keyboard(accounts, ["+ account", "Back", "Cancel"], columns=2),
            )
            return FROM_ACCOUNT
        type_map = context.user_data.get("to_type_map", {})
        if text not in type_map:
            await update.message.reply_text("Use provided buttons")
            return TO_TYPE
        type_id = type_map[text]
        context.user_data["to_type"] = type_id
        groups = self.db.account_groups(update.effective_user.id, type_id)
        context.user_data["to_group_map"] = {g["name"]: g["id"] for g in groups}
        await update.message.reply_text(
            "Select destination account group",
            reply_markup=items_reply_keyboard(groups, ["Back", "Cancel"], columns=2),
        )
        return TO_GROUP

    async def to_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        if text == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        if text == "Back":
            types = self.db.account_types()
            context.user_data["to_type_map"] = {t["name"]: t["id"] for t in types}
            await update.message.reply_text(
                "Select destination account type",
                reply_markup=items_reply_keyboard(types, ["Back", "Cancel"], columns=2),
            )
            return TO_TYPE
        group_map = context.user_data.get("to_group_map", {})
        if text not in group_map:
            await update.message.reply_text("Use provided buttons")
            return TO_GROUP
        group_id = group_map[text]
        context.user_data["to_group"] = group_id
        accounts = self.db.accounts(update.effective_user.id, group_id)
        context.user_data["to_account_map"] = {a["name"]: a["id"] for a in accounts}
        context.user_data["account_prefix"] = "to"
        await update.message.reply_text(
            "Select destination account",
            reply_markup=items_reply_keyboard(accounts, ["+ account", "Back", "Cancel"], columns=2),
        )
        return TO_ACCOUNT

    async def to_account(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        if text == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        if text == "Back":
            groups = self.db.account_groups(
                update.effective_user.id, context.user_data["to_type"]
            )
            context.user_data["to_group_map"] = {g["name"]: g["id"] for g in groups}
            await update.message.reply_text(
                "Select destination account group",
                reply_markup=items_reply_keyboard(groups, ["Back", "Cancel"], columns=2),
            )
            return TO_GROUP
        if text == "+ account":
            context.user_data["add_prefix"] = context.user_data.get("account_prefix")
            context.user_data["add_group"] = context.user_data["to_group"]
            await update.message.reply_text("Enter account name", reply_markup=ReplyKeyboardRemove())
            return ADD_ACCOUNT_NAME
        acc_map = context.user_data.get("to_account_map", {})
        if text not in acc_map:
            await update.message.reply_text("Use provided buttons")
            return TO_ACCOUNT
        account_id = acc_map[text]
        context.user_data["to_account"] = account_id
        await update.message.reply_text(
            "Enter amount",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("Back"), KeyboardButton("Cancel")]],
                resize_keyboard=True,
            ),
        )
        context.user_data.pop("editing", None)
        return AMOUNT

    async def amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        if text == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        if text == "Back":
            accounts = self.db.accounts(
                update.effective_user.id, context.user_data["to_group"]
            )
            context.user_data["to_account_map"] = {a["name"]: a["id"] for a in accounts}
            context.user_data["account_prefix"] = "to"
            await update.message.reply_text(
                "Select destination account",
                reply_markup=items_reply_keyboard(accounts, ["+ account", "Back", "Cancel"], columns=2),
            )
            return TO_ACCOUNT
        try:
            amount = float(text)
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
            f"{tx['from_name']} - {tx['amount']} -> {tx['to_name']}"
        )
        await update.message.reply_text(
            "Transaction saved", reply_markup=self.main_menu_keyboard()
        )
        return ConversationHandler.END

