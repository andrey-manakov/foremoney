from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import ContextTypes, ConversationHandler

from .init_data import seed

from .ui import items_reply_keyboard
from .transactions.helpers import make_labels, labels_map
from .states import (
    SETTINGS_MENU,
    AG_TYPE_SELECT,
    AG_GROUPS,
    AG_GROUP_RENAME,
    AG_ADD_GROUP_NAME,
    AG_ACCOUNTS,
)

class SettingsGroupsMixin:
    """Manage account group operations."""

    def account_groups_keyboard(self, labels: list[dict[str, str]]) -> ReplyKeyboardMarkup:
        return items_reply_keyboard(labels, ["+ group", "Back", "Cancel"], columns=2, extra_columns=2)

    async def start_account_groups(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = update.effective_user.id
        seed(self.db, self.db.family_id(user_id))
        types = self.db.account_types_with_value(user_id)
        type_labels = make_labels(types)
        context.user_data["ag_type_map"] = labels_map(type_labels)
        await update.message.reply_text(
            "Select account type",
            reply_markup=items_reply_keyboard(type_labels, ["Back", "Cancel"], columns=2),
        )
        return AG_TYPE_SELECT

    async def ag_type_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        if text == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            context.user_data.clear()
            return ConversationHandler.END
        if text == "Back":
            await self.start_settings(update, context)
            return SETTINGS_MENU
        type_map = context.user_data.get("ag_type_map", {})
        if text not in type_map:
            await update.message.reply_text("Use provided buttons")
            return AG_TYPE_SELECT
        type_id = type_map[text]
        context.user_data["atype"] = type_id
        groups = self.db.account_groups_with_value(update.effective_user.id, type_id)
        group_labels = make_labels(groups)
        context.user_data["ag_group_map"] = labels_map(group_labels)
        await update.message.reply_text(
            "Select group",
            reply_markup=self.account_groups_keyboard(group_labels),
        )
        return AG_GROUPS

    async def ag_add_group_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text("Enter group name", reply_markup=ReplyKeyboardRemove())
        return AG_ADD_GROUP_NAME

    async def ag_add_group_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        name = update.message.text.strip()
        if name == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            context.user_data.clear()
            return ConversationHandler.END
        user_id = update.effective_user.id
        type_id = context.user_data["atype"]
        self.db.add_account_group(user_id, type_id, name)
        groups = self.db.account_groups_with_value(user_id, type_id)
        group_labels = make_labels(groups)
        context.user_data["ag_group_map"] = labels_map(group_labels)
        await update.message.reply_text(
            "Group added",
            reply_markup=self.account_groups_keyboard(group_labels),
        )
        return AG_GROUPS

    async def ag_select_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        user_id = update.effective_user.id
        if text == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            context.user_data.clear()
            return ConversationHandler.END
        if text == "Back":
            types = self.db.account_types_with_value(user_id)
            type_labels = make_labels(types)
            context.user_data["ag_type_map"] = labels_map(type_labels)
            await update.message.reply_text(
                "Select account type",
                reply_markup=items_reply_keyboard(type_labels, ["Back"], columns=2),
            )
            return AG_TYPE_SELECT
        if text == "+ group":
            return await self.ag_add_group_prompt(update, context)
        group_map = context.user_data.get("ag_group_map", {})
        if text not in group_map:
            await update.message.reply_text("Use provided buttons")
            groups = self.db.account_groups_with_value(user_id, context.user_data.get("atype"))
            group_labels = make_labels(groups)
            context.user_data["ag_group_map"] = labels_map(group_labels)
            await update.message.reply_text(
                "Select group",
                reply_markup=self.account_groups_keyboard(group_labels),
            )
            return AG_GROUPS
        gid = group_map[text]
        context.user_data["group_id"] = gid
        keyboard = self.accounts_keyboard(user_id, gid, context.user_data)
        await update.message.reply_text("Accounts:", reply_markup=keyboard)
        return AG_ACCOUNTS

    async def ag_type_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = update.effective_user.id
        types = self.db.account_types_with_value(user_id)
        type_labels = make_labels(types)
        context.user_data["ag_type_map"] = labels_map(type_labels)
        await update.message.reply_text(
            "Select account type",
            reply_markup=items_reply_keyboard(type_labels, ["Back"], columns=2),
        )
        return AG_TYPE_SELECT

    async def groups_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = update.effective_user.id
        type_id = context.user_data["atype"]
        groups = self.db.account_groups_with_value(user_id, type_id)
        group_labels = make_labels(groups)
        context.user_data["ag_group_map"] = labels_map(group_labels)
        await update.message.reply_text(
            "Select group",
            reply_markup=self.account_groups_keyboard(group_labels),
        )
        return AG_GROUPS

    async def grename_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text("Enter new group name", reply_markup=ReplyKeyboardRemove())
        return AG_GROUP_RENAME

    async def grename(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        name = update.message.text.strip()
        if name == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            context.user_data.clear()
            return ConversationHandler.END
        gid = context.user_data["group_id"]
        user_id = update.effective_user.id
        self.db.update_account_group_name(user_id, gid, name)
        keyboard = self.accounts_keyboard(user_id, gid, context.user_data)
        await update.message.reply_text(
            "Group renamed",
            reply_markup=keyboard,
        )
        return AG_ACCOUNTS

    async def gdelete(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        gid = context.user_data["group_id"]
        user_id = update.effective_user.id
        await self._delete_group(user_id, gid)
        type_id = context.user_data["atype"]
        groups = self.db.account_groups_with_value(user_id, type_id)
        group_labels = make_labels(groups)
        context.user_data["ag_group_map"] = labels_map(group_labels)
        await update.message.reply_text(
            "Group deleted",
            reply_markup=self.account_groups_keyboard(group_labels),
        )
        return AG_GROUPS

    async def _delete_group(self, user_id: int, group_id: int) -> None:
        for acc in self.db.accounts(user_id, group_id):
            await self._delete_account(user_id, acc["id"])
        self.db.archive_account_group(user_id, group_id)
