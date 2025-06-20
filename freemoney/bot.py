from __future__ import annotations

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
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


MAIN_MENU, = range(1)


class FinanceBot:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.db = Database(self.settings.database_path)

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
        elif text == "Create transaction":
            await update.message.reply_text("Not implemented yet")
        elif text == "Transactions":
            await update.message.reply_text("Not implemented yet")
        elif text == "Settings":
            await update.message.reply_text("Not implemented yet")
        else:
            await update.message.reply_text(
                "Use menu", reply_markup=self.main_menu_keyboard()
            )

    def build_app(self) -> Application:
        application = Application.builder().token(self.settings.token).build()
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.handle_menu,
            )
        )
        return application


async def main() -> None:
    bot = FinanceBot()
    application = bot.build_app()
    await application.run_polling()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
