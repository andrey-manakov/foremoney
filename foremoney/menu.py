from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from .init_data import seed

class MenuMixin:
    """Main menu and basic commands."""

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data.clear()
        await update.message.reply_text(
            "Cancelled", reply_markup=self.main_menu_keyboard()
        )
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

    async def handle_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = update.message.text
        if text == "Dashboard":
            return await self.start_dashboard(update, context)
        elif text == "Settings":
            return await self.start_settings(update, context)
        else:
            await update.message.reply_text(
                "Use menu", reply_markup=self.main_menu_keyboard()
            )

