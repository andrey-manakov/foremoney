from __future__ import annotations

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)

from .config import get_settings
from .database import Database
from .init_data import seed
from .ui import items_keyboard


(
    FROM_TYPE,
    FROM_GROUP,
    FROM_ACCOUNT,
    TO_TYPE,
    TO_GROUP,
    TO_ACCOUNT,
    AMOUNT,
    SUMMARY,
    ADD_ACCOUNT_NAME,
) = range(9)

TX_LIST, TX_DETAILS, TX_EDIT_AMOUNT = range(9, 12)

MAIN_MENU, = range(12, 13)


class FinanceBot:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.db = Database(self.settings.database_path)

    # ----- create transaction flow -----

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

    async def summary_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        action = query.data
        user_id = update.effective_user.id
        tx_id = context.user_data.get("tx_id")
        if not tx_id:
            return ConversationHandler.END
        if action == "delete":
            self.db.delete_transaction(user_id, tx_id)
            await query.message.reply_text("Transaction deleted")
            return ConversationHandler.END
        elif action == "edit":
            context.user_data["editing"] = True
            await query.message.reply_text("Enter amount")
            return AMOUNT
        return ConversationHandler.END

    # ----- transaction list -----

    async def start_transactions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        return await self._send_transactions(update.message, update.effective_user.id, 0)

    async def _send_transactions(self, sender, user_id: int, offset: int) -> int:
        msg_obj = sender if hasattr(sender, "reply_text") else sender.message
        txs = self.db.transactions(user_id, 10, offset)
        buttons = [
            [
                InlineKeyboardButton(
                    f"{tx['from_name']} - {tx['amount']} -> {tx['to_name']}",
                    callback_data=f"tx:{tx['id']}",
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
        return TX_LIST

    async def tx_list_actions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        if query.data == "next":
            offset = context.user_data.get("tx_offset", 0) + 10
            context.user_data["tx_offset"] = offset
            await query.message.delete()
            return await self._send_transactions(query.message, user_id, offset)
        if query.data.startswith("tx:"):
            tx_id = int(query.data.split(":")[1])
            tx = self.db.transaction(user_id, tx_id)
            if not tx:
                await query.message.reply_text("Transaction not found")
                return TX_LIST
            context.user_data["tx_id"] = tx_id
            await query.message.reply_text(
                f"{tx['from_name']} - {tx['amount']} -> {tx['to_name']}",
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
                f"{tx['from_name']} - {tx['amount']} -> {tx['to_name']}",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("Edit", callback_data="edit")],
                        [InlineKeyboardButton("Delete", callback_data="delete")],
                    ]
                ),
            )
            return TX_DETAILS
        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text("Cancelled")
        return ConversationHandler.END

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        seed(self.db, user_id)
        await update.message.reply_text(
            "Welcome to FreeMoney bot!",
            reply_markup=self.main_menu_keyboard(),
        )

    def main_menu_keyboard(self) -> ReplyKeyboardMarkup:
        buttons = [
            [
                KeyboardButton("Dashboard"),
                KeyboardButton("Create transaction"),
            ],
            [
                KeyboardButton("Transactions"),
                KeyboardButton("Settings"),
            ],
        ]
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    async def handle_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = update.message.text
        if text == "Dashboard":
            await update.message.reply_text("Finance available: TODO")
        elif text == "Settings":
            await update.message.reply_text("Not implemented yet")
        else:
            await update.message.reply_text(
                "Use menu", reply_markup=self.main_menu_keyboard()
            )

    def build_app(self) -> Application:
        application = Application.builder().token(self.settings.token).build()
        application.add_handler(CommandHandler("start", self.start))
        create_tx_conv = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex("^Create transaction$"), self.start_create_transaction)],
            states={
                FROM_TYPE: [CallbackQueryHandler(self.from_type, pattern="^ftype:")],
                FROM_GROUP: [
                    CallbackQueryHandler(self.from_group, pattern="^fgroup:"),
                    CallbackQueryHandler(self.add_account_prompt, pattern="^addacc:from:"),
                ],
                FROM_ACCOUNT: [
                    CallbackQueryHandler(self.from_account, pattern="^facc:"),
                    CallbackQueryHandler(self.add_account_prompt, pattern="^addacc:from:"),
                ],
                TO_TYPE: [CallbackQueryHandler(self.to_type, pattern="^ttype:")],
                TO_GROUP: [
                    CallbackQueryHandler(self.to_group, pattern="^tgroup:"),
                    CallbackQueryHandler(self.add_account_prompt, pattern="^addacc:to:"),
                ],
                TO_ACCOUNT: [
                    CallbackQueryHandler(self.to_account, pattern="^tacc:"),
                    CallbackQueryHandler(self.add_account_prompt, pattern="^addacc:to:"),
                ],
                AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.amount)],
                ADD_ACCOUNT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_account_name)],
                SUMMARY: [CallbackQueryHandler(self.summary_action, pattern="^(edit|delete)$")],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
            per_message=True,
            allow_reentry=True,
        )
        application.add_handler(create_tx_conv)

        tx_conv = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex("^Transactions$"), self.start_transactions)],
            states={
                TX_LIST: [CallbackQueryHandler(self.tx_list_actions)],
                TX_DETAILS: [CallbackQueryHandler(self.tx_details_action)],
                TX_EDIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.tx_edit_amount)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
            per_message=True,
        )
        application.add_handler(tx_conv)

        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.handle_menu,
            )
        )
        return application


def main() -> None:
    bot = FinanceBot()
    application = bot.build_app()
    application.run_polling()


if __name__ == "__main__":
    main()
