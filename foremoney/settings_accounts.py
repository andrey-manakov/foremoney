from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .states import AG_ADD_ACCOUNT_NAME, ACCOUNT_MENU, ACCOUNT_RENAME, AG_ACCOUNTS

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

    async def _delete_account(self, user_id: int, account_id: int) -> None:
        bal = self.db.account_balance(user_id, account_id)
        if bal != 0:
            corr = self.db.correction_account(user_id)
            if bal > 0:
                self.db.add_transaction(user_id, account_id, corr, bal)
            else:
                self.db.add_transaction(user_id, corr, account_id, -bal)
        self.db.archive_account(user_id, account_id)
