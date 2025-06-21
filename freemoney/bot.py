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

SETTINGS_MENU, DASHBOARD_ACCOUNTS, AG_TYPE_SELECT, AG_GROUPS, AG_GROUP_MENU, AG_GROUP_RENAME, AG_ADD_GROUP_NAME, AG_ACCOUNTS, AG_ADD_ACCOUNT_NAME, ACCOUNT_MENU, ACCOUNT_RENAME = range(12, 23)


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

    def settings_menu_keyboard(self) -> ReplyKeyboardMarkup:
        buttons = [
            [KeyboardButton("Dashboard accounts")],
            [KeyboardButton("Account groups")],
            [KeyboardButton("Recreate database")],
            [KeyboardButton("Back")],
        ]
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    def dashboard_accounts_keyboard(self, user_id: int, selected: set[int]) -> InlineKeyboardMarkup:
        accounts = self.db.all_accounts(user_id)
        buttons = []
        for acc in accounts:
            prefix = "\u2714 " if acc["id"] in selected else ""
            label = f"{prefix}{acc['group_name']}: {acc['name']}"
            buttons.append([InlineKeyboardButton(label, callback_data=f"dashacc:{acc['id']}")])
        buttons.append([InlineKeyboardButton("Save", callback_data="dashsave")])
        return InlineKeyboardMarkup(buttons)

    def account_groups_keyboard(self, user_id: int, type_id: int) -> InlineKeyboardMarkup:
        groups = self.db.account_groups(user_id, type_id)
        buttons = [
            [InlineKeyboardButton(g["name"], callback_data=f"aggroup:{g['id']}")]
            for g in groups
        ]
        buttons.append([InlineKeyboardButton("+ group", callback_data="agaddgroup")])
        buttons.append([InlineKeyboardButton("Back", callback_data="agtypeback")])
        return InlineKeyboardMarkup(buttons)

    def accounts_keyboard(self, user_id: int, group_id: int) -> InlineKeyboardMarkup:
        accs = self.db.accounts(user_id, group_id)
        buttons = [
            [InlineKeyboardButton(a["name"], callback_data=f"acc:{a['id']}")]
            for a in accs
        ]
        buttons.append([InlineKeyboardButton("+ account", callback_data="addacc")])
        buttons.append([InlineKeyboardButton("Rename group", callback_data="grename")])
        buttons.append([InlineKeyboardButton("Delete group", callback_data="gdelete")])
        buttons.append([InlineKeyboardButton("Back", callback_data="groupsback")])
        return InlineKeyboardMarkup(buttons)

    async def handle_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = update.message.text
        if text == "Dashboard":
            await self.show_dashboard(update, context)
        elif text == "Settings":
            return await self.start_settings(update, context)
        else:
            await update.message.reply_text(
                "Use menu", reply_markup=self.main_menu_keyboard()
            )

    async def show_dashboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        val = self.db.get_setting(user_id, "dashboard_accounts")
        if not val:
            await update.message.reply_text(
                "No accounts selected for dashboard. Use Settings to configure."
            )
            return
        account_ids = [int(v) for v in val.split(",") if v]
        total = self.db.accounts_balance(user_id, account_ids)
        await update.message.reply_text(f"Finance available: {total}")

    async def start_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text(
            "Settings:", reply_markup=self.settings_menu_keyboard()
        )
        return SETTINGS_MENU

    async def settings_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        if text == "Dashboard accounts":
            return await self.start_dashboard_accounts(update, context)
        if text == "Account groups":
            return await self.start_account_groups(update, context)
        if text == "Recreate database":
            return await self.recreate_database(update, context)
        if text == "Back":
            await update.message.reply_text(
                "Back to menu", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        await update.message.reply_text("Use menu", reply_markup=self.settings_menu_keyboard())
        return SETTINGS_MENU

    async def start_dashboard_accounts(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = update.effective_user.id
        val = self.db.get_setting(user_id, "dashboard_accounts") or ""
        selected = set(int(v) for v in val.split(",") if v)
        context.user_data["dash_sel"] = selected
        await update.message.reply_text(
            "Select accounts:",
            reply_markup=self.dashboard_accounts_keyboard(user_id, selected),
        )
        return DASHBOARD_ACCOUNTS

    async def toggle_dashboard_account(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        aid = int(query.data.split(":")[1])
        selected: set[int] = context.user_data.get("dash_sel", set())
        if aid in selected:
            selected.remove(aid)
        else:
            selected.add(aid)
        context.user_data["dash_sel"] = selected
        await query.edit_message_reply_markup(
            reply_markup=self.dashboard_accounts_keyboard(update.effective_user.id, selected)
        )
        return DASHBOARD_ACCOUNTS

    async def save_dashboard_accounts(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        selected: set[int] = context.user_data.get("dash_sel", set())
        val = ",".join(str(v) for v in selected)
        self.db.set_setting(user_id, "dashboard_accounts", val)
        await query.message.reply_text("Saved", reply_markup=self.settings_menu_keyboard())
        return SETTINGS_MENU

    async def recreate_database(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = update.effective_user.id
        self.db.conn.close()
        if self.settings.database_path.exists():
            self.settings.database_path.unlink()
        self.db = Database(self.settings.database_path)
        seed(self.db, user_id)
        await update.message.reply_text("Database recreated")
        return SETTINGS_MENU

    async def start_account_groups(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        types = self.db.account_types()
        await update.message.reply_text(
            "Select account type", reply_markup=items_keyboard(types, "agtype")
        )
        return AG_TYPE_SELECT

    async def ag_type_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        type_id = int(query.data.split(":")[1])
        context.user_data["atype"] = type_id
        await query.message.reply_text(
            "Select group",
            reply_markup=self.account_groups_keyboard(update.effective_user.id, type_id),
        )
        return AG_GROUPS

    async def ag_add_group_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        await query.message.reply_text("Enter group name")
        return AG_ADD_GROUP_NAME

    async def ag_add_group_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        name = update.message.text.strip()
        user_id = update.effective_user.id
        type_id = context.user_data["atype"]
        self.db.add_account_group(user_id, type_id, name)
        await update.message.reply_text(
            "Group added",
            reply_markup=self.account_groups_keyboard(user_id, type_id),
        )
        return AG_GROUPS

    async def ag_select_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        gid = int(query.data.split(":")[1])
        context.user_data["group_id"] = gid
        await query.message.reply_text(
            "Accounts:",
            reply_markup=self.accounts_keyboard(update.effective_user.id, gid),
        )
        return AG_ACCOUNTS

    async def ag_type_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        types = self.db.account_types()
        await query.message.reply_text(
            "Select account type",
            reply_markup=items_keyboard(types, "agtype"),
        )
        return AG_TYPE_SELECT

    async def groups_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        type_id = context.user_data["atype"]
        await query.message.reply_text(
            "Select group",
            reply_markup=self.account_groups_keyboard(update.effective_user.id, type_id),
        )
        return AG_GROUPS

    async def grename_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        await query.message.reply_text("Enter new group name")
        return AG_GROUP_RENAME

    async def grename(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        name = update.message.text.strip()
        gid = context.user_data["group_id"]
        user_id = update.effective_user.id
        self.db.update_account_group_name(user_id, gid, name)
        await update.message.reply_text(
            "Group renamed",
            reply_markup=self.accounts_keyboard(user_id, gid),
        )
        return AG_ACCOUNTS

    async def gdelete(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        gid = context.user_data["group_id"]
        user_id = update.effective_user.id
        await self._delete_group(user_id, gid)
        type_id = context.user_data["atype"]
        await query.message.reply_text(
            "Group deleted",
            reply_markup=self.account_groups_keyboard(user_id, type_id),
        )
        return AG_GROUPS

    async def acc_select(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        aid = int(query.data.split(":")[1])
        context.user_data["account_id"] = aid
        await query.message.reply_text(
            "Account menu",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Rename", callback_data="renacc")],
                [InlineKeyboardButton("Delete", callback_data="delacc")],
                [InlineKeyboardButton("Back", callback_data="accback")],
            ]),
        )
        return ACCOUNT_MENU

    async def acc_add_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        await query.message.reply_text("Enter account name")
        return AG_ADD_ACCOUNT_NAME

    async def acc_add_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        name = update.message.text.strip()
        gid = context.user_data["group_id"]
        user_id = update.effective_user.id
        self.db.add_account(user_id, gid, name)
        await update.message.reply_text(
            "Account added",
            reply_markup=self.accounts_keyboard(user_id, gid),
        )
        return AG_ACCOUNTS

    async def account_rename_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        await query.message.reply_text("Enter new name")
        return ACCOUNT_RENAME

    async def account_rename(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        name = update.message.text.strip()
        aid = context.user_data["account_id"]
        user_id = update.effective_user.id
        self.db.update_account_name(user_id, aid, name)
        gid = context.user_data["group_id"]
        await update.message.reply_text(
            "Account renamed",
            reply_markup=self.accounts_keyboard(user_id, gid),
        )
        return AG_ACCOUNTS

    async def account_delete(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        aid = context.user_data["account_id"]
        gid = context.user_data["group_id"]
        user_id = update.effective_user.id
        await self._delete_account(user_id, aid)
        await query.message.reply_text(
            "Account deleted",
            reply_markup=self.accounts_keyboard(user_id, gid),
        )
        return AG_ACCOUNTS

    async def account_menu_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        gid = context.user_data["group_id"]
        await query.message.reply_text(
            "Accounts:",
            reply_markup=self.accounts_keyboard(update.effective_user.id, gid),
        )
        return AG_ACCOUNTS

    # ----- helpers for deleting with correction -----
    async def _delete_account(self, user_id: int, account_id: int) -> None:
        bal = self.db.account_balance(user_id, account_id)
        if bal != 0:
            corr = self.db.correction_account(user_id)
            if bal > 0:
                self.db.add_transaction(user_id, account_id, corr, bal)
            else:
                self.db.add_transaction(user_id, corr, account_id, -bal)
        self.db.archive_account(user_id, account_id)

    async def _delete_group(self, user_id: int, group_id: int) -> None:
        for acc in self.db.accounts(user_id, group_id):
            await self._delete_account(user_id, acc["id"])
        self.db.archive_account_group(user_id, group_id)

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

        settings_conv = ConversationHandler(
            entry_points=[
                MessageHandler(filters.Regex("^Settings$"), self.start_settings),
                CallbackQueryHandler(self.start_settings, pattern="^opensettings$")
            ],
            states={
                SETTINGS_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.settings_menu)],
                DASHBOARD_ACCOUNTS: [
                    CallbackQueryHandler(self.toggle_dashboard_account, pattern="^dashacc:"),
                    CallbackQueryHandler(self.save_dashboard_accounts, pattern="^dashsave$")
                ],
                AG_TYPE_SELECT: [
                    CallbackQueryHandler(self.ag_type_selected, pattern="^agtype:")
                ],
                AG_GROUPS: [
                    CallbackQueryHandler(self.ag_select_group, pattern="^aggroup:"),
                    CallbackQueryHandler(self.ag_add_group_prompt, pattern="^agaddgroup$"),
                    CallbackQueryHandler(self.ag_type_back, pattern="^agtypeback$")
                ],
                AG_ADD_GROUP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.ag_add_group_name)],
                AG_ACCOUNTS: [
                    CallbackQueryHandler(self.acc_select, pattern="^acc:"),
                    CallbackQueryHandler(self.acc_add_prompt, pattern="^addacc$"),
                    CallbackQueryHandler(self.grename_prompt, pattern="^grename$"),
                    CallbackQueryHandler(self.gdelete, pattern="^gdelete$"),
                    CallbackQueryHandler(self.groups_back, pattern="^groupsback$")
                ],
                AG_GROUP_RENAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.grename)],
                AG_ADD_ACCOUNT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.acc_add_name)],
                ACCOUNT_MENU: [
                    CallbackQueryHandler(self.account_rename_prompt, pattern="^renacc$"),
                    CallbackQueryHandler(self.account_delete, pattern="^delacc$"),
                    CallbackQueryHandler(self.account_menu_back, pattern="^accback$")
                ],
                ACCOUNT_RENAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.account_rename)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
            per_message=True,
        )
        application.add_handler(settings_conv)

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
