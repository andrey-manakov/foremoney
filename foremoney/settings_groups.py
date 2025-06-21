from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .init_data import seed

from .ui import items_keyboard
from .states import (
    AG_TYPE_SELECT, AG_GROUPS, AG_GROUP_RENAME, AG_ADD_GROUP_NAME,
    AG_ACCOUNTS,
)

class SettingsGroupsMixin:
    """Manage account group operations."""

    def account_groups_keyboard(self, user_id: int, type_id: int) -> InlineKeyboardMarkup:
        groups = self.db.account_groups_with_value(user_id, type_id)
        buttons = [
            [InlineKeyboardButton(f"{g['name']} ({g['value']})", callback_data=f"aggroup:{g['id']}")]
            for g in groups
        ]
        buttons.append([InlineKeyboardButton("+ group", callback_data="agaddgroup")])
        buttons.append([InlineKeyboardButton("Back", callback_data="agtypeback")])
        return InlineKeyboardMarkup(buttons)

    async def start_account_groups(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = update.effective_user.id
        seed(self.db, user_id)
        types = self.db.account_types_with_value(user_id)
        type_labels = [
            {"id": t["id"], "name": f"{t['name']} ({t['value']})"} for t in types
        ]
        await update.message.reply_text(
            "Select account type", reply_markup=items_keyboard(type_labels, "agtype")
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
        types = self.db.account_types_with_value(update.effective_user.id)
        type_labels = [
            {"id": t["id"], "name": f"{t['name']} ({t['value']})"} for t in types
        ]
        await query.message.reply_text(
            "Select account type",
            reply_markup=items_keyboard(type_labels, "agtype"),
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

    async def _delete_group(self, user_id: int, group_id: int) -> None:
        for acc in self.db.accounts(user_id, group_id):
            await self._delete_account(user_id, acc["id"])
        self.db.archive_account_group(user_id, group_id)
