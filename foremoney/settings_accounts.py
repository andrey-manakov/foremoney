from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .states import (
    AG_ADD_ACCOUNT_NAME,
    AG_ADD_ACCOUNT_VALUE,
    ACCOUNT_MENU,
    ACCOUNT_RENAME,
    AG_ACCOUNTS,
)

class SettingsAccountsMixin:
    """Manage individual accounts."""

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
        acc_id = self.db.add_account(user_id, gid, name)
        context.user_data["new_account_id"] = acc_id
        await update.message.reply_text("Enter initial value")
        return AG_ADD_ACCOUNT_VALUE

    async def acc_add_value(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text.strip()
        try:
            value = float(text)
        except ValueError:
            await update.message.reply_text("Please enter a number")
            return AG_ADD_ACCOUNT_VALUE
        aid = context.user_data.pop("new_account_id")
        gid = context.user_data["group_id"]
        user_id = update.effective_user.id
        if value != 0:
            row = self.db.fetchone(
                """
                SELECT g.name AS group_name, t.name AS type_name
                FROM account_groups g
                JOIN account_types t ON g.type_id=t.id
                WHERE g.id=? AND g.user_id=?
                """,
                (gid, user_id),
            )
            if row:
                gname = row["group_name"]
                tname = row["type_name"]
                if tname == "assets":
                    cap = self.db.fetchone(
                        """
                        SELECT a.id FROM accounts a
                        JOIN account_groups g ON a.group_id=g.id
                        JOIN account_types t ON g.type_id=t.id
                        WHERE a.user_id=? AND t.name='capital' AND g.name='assets' AND a.name=?
                        """,
                        (user_id, gname),
                    )
                    if cap:
                        self.db.add_transaction(user_id, cap["id"], aid, value)
                elif tname == "liabilities":
                    cap = self.db.fetchone(
                        """
                        SELECT a.id FROM accounts a
                        JOIN account_groups g ON a.group_id=g.id
                        JOIN account_types t ON g.type_id=t.id
                        WHERE a.user_id=? AND t.name='capital' AND g.name='liabilities' AND a.name=?
                        """,
                        (user_id, gname),
                    )
                    if cap:
                        self.db.add_transaction(user_id, aid, cap["id"], value)
                elif tname == "expenditures":
                    cap = self.db.fetchone(
                        """
                        SELECT a.id FROM accounts a
                        JOIN account_groups g ON a.group_id=g.id
                        JOIN account_types t ON g.type_id=t.id
                        WHERE a.user_id=? AND t.name='capital' AND g.name='expenditures' AND a.name=?
                        """,
                        (user_id, gname),
                    )
                    if cap:
                        self.db.add_transaction(user_id, cap["id"], aid, value)
                elif tname == "income":
                    cap = self.db.fetchone(
                        """
                        SELECT a.id FROM accounts a
                        JOIN account_groups g ON a.group_id=g.id
                        JOIN account_types t ON g.type_id=t.id
                        WHERE a.user_id=? AND t.name='capital' AND g.name='income' AND a.name=?
                        """,
                        (user_id, gname),
                    )
                    if cap:
                        self.db.add_transaction(user_id, aid, cap["id"], value)
                elif tname == "capital":
                    cap_id = self.db.correction_account(user_id)
                    self.db.add_transaction(user_id, aid, cap_id, value)
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

    async def _delete_account(self, user_id: int, account_id: int) -> None:
        bal = self.db.account_balance(user_id, account_id)
        if bal != 0:
            corr = self.db.correction_account(user_id)
            if bal > 0:
                self.db.add_transaction(user_id, account_id, corr, bal)
            else:
                self.db.add_transaction(user_id, corr, account_id, -bal)
        self.db.archive_account(user_id, account_id)
