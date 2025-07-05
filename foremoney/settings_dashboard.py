from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InputFile,
)
from telegram.ext import ContextTypes, ConversationHandler
from io import BytesIO

from .states import SETTINGS_MENU, DASHBOARD_ACCOUNTS, IMPORT_WAIT_FILE
from .database import Database, export_archive, import_archive
from .init_data import seed

class SettingsDashboardMixin:
    """Manage dashboard accounts and database."""

    def settings_menu_keyboard(self) -> ReplyKeyboardMarkup:
        buttons = [
            [
                KeyboardButton("Dashboard accounts"),
                KeyboardButton("Accounts"),
            ],
            [
                KeyboardButton("Add family"),
                KeyboardButton("Recreate database"),
            ],
            [
                KeyboardButton("Export data"),
                KeyboardButton("Import data"),
            ],
            [
                KeyboardButton("Back"),
            ],
        ]
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    async def start_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text(
            "Settings:", reply_markup=self.settings_menu_keyboard()
        )
        return SETTINGS_MENU

    async def settings_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        if text == "Dashboard accounts":
            return await self.start_dashboard_accounts(update, context)
        if text == "Accounts":
            return await self.start_account_groups(update, context)
        if text == "Add family":
            return await self.invite_family(update, context)
        if text == "Recreate database":
            return await self.recreate_database(update, context)
        if text == "Export data":
            return await self.export_data(update, context)
        if text == "Import data":
            return await self.import_data_prompt(update, context)
        if text == "Back":
            await update.message.reply_text(
                "Back to menu", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        await update.message.reply_text("Use menu", reply_markup=self.settings_menu_keyboard())
        return SETTINGS_MENU

    def dashboard_accounts_keyboard(self, user_id: int, selected: set[int]) -> InlineKeyboardMarkup:
        accounts = self.db.all_accounts(user_id)
        buttons = []
        for acc in accounts:
            prefix = "\u2714 " if acc["id"] in selected else ""
            label = f"{prefix}{acc['group_name']}: {acc['name']}"
            buttons.append([InlineKeyboardButton(label, callback_data=f"dashacc:{acc['id']}")])
        buttons.append([InlineKeyboardButton("Save", callback_data="dashsave")])
        buttons.append([InlineKeyboardButton("Cancel", callback_data="dashcancel")])
        return InlineKeyboardMarkup(buttons)

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

    async def cancel_settings_submenu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        if query:
            await query.answer()
            await query.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
        else:
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
        context.user_data.clear()
        return ConversationHandler.END

    async def recreate_database(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = update.effective_user.id
        self.db.conn.close()
        if self.settings.database_path.exists():
            self.settings.database_path.unlink()
        self.db = Database(self.settings.database_path)
        seed(self.db, self.db.family_id(user_id))
        await update.message.reply_text("Database recreated")
        return SETTINGS_MENU

    async def export_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        data = export_archive(self.settings.database_path)
        await update.message.reply_document(
            InputFile(BytesIO(data), filename="foremoney_export.zip")
        )
        return SETTINGS_MENU

    async def import_data_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text(
            "Send ZIP archive to import. Current database will be replaced."
        )
        return IMPORT_WAIT_FILE

    async def import_data_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        doc = update.message.document
        if not doc:
            await update.message.reply_text("Please send a ZIP archive")
            return IMPORT_WAIT_FILE
        file = await doc.get_file()
        buf = BytesIO()
        await file.download_to_memory(buf)
        buf.seek(0)
        import_archive(self.settings.database_path, buf.getvalue())
        self.db = Database(self.settings.database_path)
        await update.message.reply_text(
            "Database imported", reply_markup=self.settings_menu_keyboard()
        )
        return SETTINGS_MENU
