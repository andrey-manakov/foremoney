from telegram import Update
from telegram.ext import ContextTypes
from .states import SETTINGS_MENU

class SettingsFamilyMixin:
    """Family invitation management."""

    async def invite_family(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = update.effective_user.id
        family_id = self.db.family_id(user_id)
        token = self.db.create_family_invite(family_id)
        bot_username = (await context.bot.get_me()).username
        link = f"https://t.me/{bot_username}?start=join_{token}"
        await update.message.reply_text(
            "Forward this message to a family member to join your finances:\n" + link
        )
        return SETTINGS_MENU

