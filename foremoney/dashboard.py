from __future__ import annotations

from datetime import datetime
from io import BytesIO

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
import matplotlib.pyplot as plt

from .init_data import seed
from .states import (
    DASH_MENU,
    DASH_ACC_TYPE,
    DASH_ACC_MENU,
    DASH_GROUP_SELECT,
    DASH_GROUP_MENU,
)
from .ui import items_reply_keyboard
from .transactions.helpers import make_labels, labels_map


class DashboardMixin:
    """Dashboard views and charts."""

    def dashboard_menu_keyboard(self) -> ReplyKeyboardMarkup:
        buttons = [
            [KeyboardButton("Cash available"), KeyboardButton("Accounts")],
            [KeyboardButton("Forecast"), KeyboardButton("Back")],
        ]
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    def dashboard_account_menu_keyboard(self) -> ReplyKeyboardMarkup:
        buttons = [
            [KeyboardButton("Account groups"), KeyboardButton("Structure")],
            [KeyboardButton("Dynamics"), KeyboardButton("Back")],
            [KeyboardButton("Cancel")],
        ]
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    def dashboard_group_menu_keyboard(self) -> ReplyKeyboardMarkup:
        buttons = [
            [KeyboardButton("Accounts"), KeyboardButton("Structure")],
            [KeyboardButton("Dynamics"), KeyboardButton("Back")],
            [KeyboardButton("Cancel")],
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
            type_labels = make_labels(types)
            context.user_data["dash_type_map"] = labels_map(type_labels)
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
            type_labels = make_labels(types)
            context.user_data["dash_type_map"] = labels_map(type_labels)
            await update.message.reply_text(
                "Select account type",
                reply_markup=items_reply_keyboard(
                    type_labels, ["Back", "Cancel"], columns=2
                ),
            )
            return DASH_ACC_TYPE
        if text == "Account groups":
            return await self.dashboard_group_list(update, context)
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

    async def dashboard_group_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = update.effective_user.id
        type_id = context.user_data.get("dash_type")
        groups = self.db.account_groups_with_value(user_id, type_id)
        group_labels = make_labels(groups)
        context.user_data["dash_group_map"] = labels_map(group_labels)
        await update.message.reply_text(
            "Select account group",
            reply_markup=items_reply_keyboard(group_labels, ["Back", "Cancel"], columns=2),
        )
        return DASH_GROUP_SELECT

    async def dashboard_group_select(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        if text == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        if text == "Back":
            await update.message.reply_text(
                "Account view:", reply_markup=self.dashboard_account_menu_keyboard()
            )
            return DASH_ACC_MENU
        group_map = context.user_data.get("dash_group_map", {})
        if text not in group_map:
            await update.message.reply_text("Use provided buttons")
            return DASH_GROUP_SELECT
        gid = group_map[text]
        context.user_data["dash_group"] = gid
        await update.message.reply_text(
            "Group view:", reply_markup=self.dashboard_group_menu_keyboard()
        )
        return DASH_GROUP_MENU

    async def dashboard_group_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        user_id = update.effective_user.id
        gid = context.user_data.get("dash_group")
        if text == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        if text == "Back":
            return await self.dashboard_group_list(update, context)
        if text == "Accounts":
            accounts = self.db.accounts_with_value(user_id, gid)
            if not accounts:
                await update.message.reply_text(
                    "No accounts to display", reply_markup=self.dashboard_group_menu_keyboard()
                )
                return DASH_GROUP_MENU
            lines = [f"{a['name']}: {a['value']}" for a in accounts]
            await update.message.reply_text(
                "\n".join(lines), reply_markup=self.dashboard_group_menu_keyboard()
            )
            return DASH_GROUP_MENU
        if text == "Structure":
            accounts = self.db.accounts_with_value(user_id, gid)
            if not accounts:
                await update.message.reply_text(
                    "No data to display", reply_markup=self.dashboard_group_menu_keyboard()
                )
                return DASH_GROUP_MENU
            names = [a["name"] for a in accounts]
            values = [a["value"] for a in accounts]
            if sum(values) == 0:
                await update.message.reply_text(
                    "No data to display", reply_markup=self.dashboard_group_menu_keyboard()
                )
                return DASH_GROUP_MENU
            plt.figure()
            plt.pie(values, labels=names, autopct="%1.1f%%")
            buf = BytesIO()
            plt.savefig(buf, format="png")
            plt.close()
            buf.seek(0)
            await update.message.reply_photo(photo=buf, reply_markup=self.dashboard_group_menu_keyboard())
            return DASH_GROUP_MENU
        if text == "Dynamics":
            rows = self.db.account_group_transactions(user_id, gid)
            if not rows:
                await update.message.reply_text(
                    "No data to display", reply_markup=self.dashboard_group_menu_keyboard()
                )
                return DASH_GROUP_MENU
            neg_types = {"liabilities", "income", "capital"}
            times = []
            values = []
            val = 0.0
            for r in rows:
                delta = 0.0
                if r["from_group_id"] == gid:
                    delta += r["amount"] if r["from_type"] in neg_types else -r["amount"]
                if r["to_group_id"] == gid:
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
            await update.message.reply_photo(photo=buf, reply_markup=self.dashboard_group_menu_keyboard())
            return DASH_GROUP_MENU
        await update.message.reply_text(
            "Use menu", reply_markup=self.dashboard_group_menu_keyboard()
        )
        return DASH_GROUP_MENU
