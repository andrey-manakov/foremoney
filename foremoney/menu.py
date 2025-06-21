from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from .init_data import seed
from .states import SETTINGS_MENU

class MenuMixin:
    """Main menu and basic commands."""

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text("Cancelled")
        return ConversationHandler.END

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        seed(self.db, user_id)
        await update.message.reply_text(
            "Welcome to ForeMoney bot!",
            reply_markup=self.main_menu_keyboard(),
        )

    def main_menu_keyboard(self) -> ReplyKeyboardMarkup:
        buttons = [
            [KeyboardButton("Dashboard"), KeyboardButton("Create transaction")],
            [KeyboardButton("Transactions"), KeyboardButton("Settings")],
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
