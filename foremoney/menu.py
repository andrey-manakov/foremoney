from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from .init_data import seed
from .states import (
    SETTINGS_MENU,
    DASH_MENU,
    DASH_ACC_TYPE,
    DASH_ACC_MENU,
)
from .ui import items_reply_keyboard
from datetime import datetime
from io import BytesIO
import matplotlib.pyplot as plt

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
            return await self.start_dashboard(update, context)
        elif text == "Settings":
            return await self.start_settings(update, context)
        else:
            await update.message.reply_text(
                "Use menu", reply_markup=self.main_menu_keyboard()
            )

    def dashboard_menu_keyboard(self) -> ReplyKeyboardMarkup:
        buttons = [
            [KeyboardButton("Cash available"), KeyboardButton("Accounts")],
            [KeyboardButton("Forecast"), KeyboardButton("Back")],
        ]
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    def dashboard_account_menu_keyboard(self) -> ReplyKeyboardMarkup:
        buttons = [
            [KeyboardButton("Account groups")],
            [KeyboardButton("Structure")],
            [KeyboardButton("Dynamics")],
            [KeyboardButton("Back"), KeyboardButton("Cancel")],
        ]
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    async def start_dashboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text(
            "Dashboard:", reply_markup=self.dashboard_menu_keyboard()
        )
        return DASH_MENU

    async def dashboard_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        user_id = update.effective_user.id
        if text == "Cash available":
            val = self.db.get_setting(user_id, "dashboard_accounts")
            if not val:
                await update.message.reply_text(
                    "No accounts selected for dashboard. Use Settings to configure."
                )
                return DASH_MENU
            account_ids = [int(v) for v in val.split(",") if v]
            total = self.db.accounts_balance(user_id, account_ids)
            await update.message.reply_text(
                f"Finance available: {total}", reply_markup=self.dashboard_menu_keyboard()
            )
            return DASH_MENU
        if text == "Accounts":
            seed(self.db, user_id)
            types = self.db.account_types_with_value(user_id)
            type_labels = [
                {"id": t["id"], "name": f"{t['name']} ({t['value']})"} for t in types
            ]
            context.user_data["dash_type_map"] = {lbl["name"]: lbl["id"] for lbl in type_labels}
            await update.message.reply_text(
                "Select account type",
                reply_markup=items_reply_keyboard(
                    type_labels, ["Back", "Cancel"], columns=2
                ),
            )
            return DASH_ACC_TYPE
        if text == "Forecast":
            await update.message.reply_text(
                "Forecast feature is not implemented yet.",
                reply_markup=self.dashboard_menu_keyboard(),
            )
            return DASH_MENU
        if text == "Back":
            await update.message.reply_text(
                "Back to menu", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        await update.message.reply_text(
            "Use menu", reply_markup=self.dashboard_menu_keyboard()
        )
        return DASH_MENU

    async def dashboard_acc_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        if text == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        if text == "Back":
            await update.message.reply_text(
                "Dashboard:", reply_markup=self.dashboard_menu_keyboard()
            )
            return DASH_MENU
        type_map = context.user_data.get("dash_type_map", {})
        if text not in type_map:
            await update.message.reply_text("Use provided buttons")
            return DASH_ACC_TYPE
        type_id = type_map[text]
        context.user_data["dash_type"] = type_id
        await update.message.reply_text(
            "Account view:", reply_markup=self.dashboard_account_menu_keyboard()
        )
        return DASH_ACC_MENU

    async def dashboard_acc_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        user_id = update.effective_user.id
        type_id = context.user_data.get("dash_type")
        if text == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        if text == "Back":
            types = self.db.account_types_with_value(user_id)
            type_labels = [
                {"id": t["id"], "name": f"{t['name']} ({t['value']})"} for t in types
            ]
            context.user_data["dash_type_map"] = {lbl["name"]: lbl["id"] for lbl in type_labels}
            await update.message.reply_text(
                "Select account type",
                reply_markup=items_reply_keyboard(
                    type_labels, ["Back", "Cancel"], columns=2
                ),
            )
            return DASH_ACC_TYPE
        if text == "Account groups":
            await update.message.reply_text(
                "Feature not implemented yet.", reply_markup=self.dashboard_account_menu_keyboard()
            )
            return DASH_ACC_MENU
        if text == "Structure":
            groups = self.db.account_groups_with_value(user_id, type_id)
            if not groups:
                await update.message.reply_text(
                    "No data to display", reply_markup=self.dashboard_account_menu_keyboard()
                )
                return DASH_ACC_MENU
            names = [g["name"] for g in groups]
            values = [g["value"] for g in groups]
            if sum(values) == 0:
                await update.message.reply_text(
                    "No data to display", reply_markup=self.dashboard_account_menu_keyboard()
                )
                return DASH_ACC_MENU
            plt.figure()
            plt.pie(values, labels=names, autopct="%1.1f%%")
            buf = BytesIO()
            plt.savefig(buf, format="png")
            plt.close()
            buf.seek(0)
            await update.message.reply_photo(photo=buf, reply_markup=self.dashboard_account_menu_keyboard())
            return DASH_ACC_MENU
        if text == "Dynamics":
            rows = self.db.account_type_transactions(user_id, type_id)
            if not rows:
                await update.message.reply_text(
                    "No data to display", reply_markup=self.dashboard_account_menu_keyboard()
                )
                return DASH_ACC_MENU
            neg_types = {"liabilities", "income", "capital"}
            times = []
            values = []
            val = 0.0
            for r in rows:
                delta = 0.0
                if r["from_type_id"] == type_id:
                    delta += r["amount"] if r["from_type"] in neg_types else -r["amount"]
                if r["to_type_id"] == type_id:
                    delta += -r["amount"] if r["to_type"] in neg_types else r["amount"]
                val += delta
                times.append(datetime.fromisoformat(r["ts"]))
                values.append(val)
            plt.figure()
            plt.plot(times, values)
            plt.xticks(rotation=45)
            plt.tight_layout()
            buf = BytesIO()
            plt.savefig(buf, format="png")
            plt.close()
            buf.seek(0)
            await update.message.reply_photo(photo=buf, reply_markup=self.dashboard_account_menu_keyboard())
            return DASH_ACC_MENU
        await update.message.reply_text(
            "Use menu", reply_markup=self.dashboard_account_menu_keyboard()
        )
        return DASH_ACC_MENU
