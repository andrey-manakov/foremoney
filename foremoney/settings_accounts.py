from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
)
from telegram.ext import ContextTypes

from .ui import items_reply_keyboard

from .states import (
    AG_ADD_ACCOUNT_NAME,
    AG_ADD_ACCOUNT_VALUE,
    ACCOUNT_MENU,
    ACCOUNT_RENAME,
    AG_ACCOUNTS,
)

class SettingsAccountsMixin:
    """Manage individual accounts."""

    def accounts_keyboard(self, user_id: int, group_id: int, udata: dict) -> ReplyKeyboardMarkup:
        accs = self.db.accounts(user_id, group_id)
        labels = [{"id": a["id"], "name": a["name"]} for a in accs]
        udata["ag_account_map"] = {lbl["name"]: lbl["id"] for lbl in labels}
        row = self.db.fetchone(
            """
            SELECT t.name AS type_name
            FROM account_groups g
            JOIN account_types t ON g.type_id=t.id
            WHERE g.id=? AND g.user_id=?
            """,
            (group_id, user_id),
        )
        extra: list[str] = []
        if not row or row["type_name"] != "capital":
            extra.append("+ account")
        extra.extend(["Rename group", "Delete group", "Back"])
        return items_reply_keyboard(labels, extra, columns=2)

    async def acc_select(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        acc_map = context.user_data.get("ag_account_map", {})
        if text not in acc_map:
            await update.message.reply_text("Use provided buttons")
            gid = context.user_data["group_id"]
            keyboard = self.accounts_keyboard(update.effective_user.id, gid, context.user_data)
            await update.message.reply_text("Accounts:", reply_markup=keyboard)
            return AG_ACCOUNTS
        aid = acc_map[text]
        context.user_data["account_id"] = aid
        await update.message.reply_text(
            "Account menu",
            reply_markup=ReplyKeyboardMarkup(
                [
                    [KeyboardButton("Rename")],
                    [KeyboardButton("Delete")],
                    [KeyboardButton("Back")],
                ],
                resize_keyboard=True,
            ),
        )
        return ACCOUNT_MENU

    async def acc_add_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        gid = context.user_data["group_id"]
        row = self.db.fetchone(
            """
            SELECT t.name AS type_name
            FROM account_groups g
            JOIN account_types t ON g.type_id=t.id
            WHERE g.id=? AND g.user_id=?
            """,
            (gid, update.effective_user.id),
        )
        if row and row["type_name"] == "capital":
            await update.message.reply_text("Cannot create accounts in capital type")
            keyboard = self.accounts_keyboard(update.effective_user.id, gid, context.user_data)
            await update.message.reply_text("Accounts:", reply_markup=keyboard)
            return AG_ACCOUNTS
        await update.message.reply_text("Enter account name", reply_markup=ReplyKeyboardRemove())
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
        keyboard = self.accounts_keyboard(user_id, gid, context.user_data)
        await update.message.reply_text(
            "Account added",
            reply_markup=keyboard,
        )
        return AG_ACCOUNTS

    async def account_rename_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text("Enter new name", reply_markup=ReplyKeyboardRemove())
        return ACCOUNT_RENAME

    async def account_rename(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        name = update.message.text.strip()
        aid = context.user_data["account_id"]
        user_id = update.effective_user.id
        self.db.update_account_name(user_id, aid, name)
        gid = context.user_data["group_id"]
        keyboard = self.accounts_keyboard(user_id, gid, context.user_data)
        await update.message.reply_text(
            "Account renamed",
            reply_markup=keyboard,
        )
        return AG_ACCOUNTS

    async def account_delete(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        aid = context.user_data["account_id"]
        gid = context.user_data["group_id"]
        user_id = update.effective_user.id
        await self._delete_account(user_id, aid)
        keyboard = self.accounts_keyboard(user_id, gid, context.user_data)
        await update.message.reply_text(
            "Account deleted",
            reply_markup=keyboard,
        )
        return AG_ACCOUNTS

    async def account_menu_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        gid = context.user_data["group_id"]
        keyboard = self.accounts_keyboard(update.effective_user.id, gid, context.user_data)
        await update.message.reply_text(
            "Accounts:",
            reply_markup=keyboard,
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
