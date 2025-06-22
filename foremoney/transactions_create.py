from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import ContextTypes, ConversationHandler

from .ui import items_reply_keyboard
from .init_data import seed
from .states import (
    FROM_TYPE,
    FROM_GROUP,
    FROM_ACCOUNT,
    TO_TYPE,
    TO_GROUP,
    TO_ACCOUNT,
    AMOUNT,
    ADD_ACCOUNT_NAME,
    ADD_ACCOUNT_VALUE,
    TX_DATETIME,
)

class TransactionCreateMixin:
    """Flow for creating a transaction."""

    async def start_create_transaction(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = update.effective_user.id
        seed(self.db, user_id)
        types = self.db.account_types_with_value(user_id)
        type_labels = [
            {"id": t["id"], "name": f"{t['name']} ({t['value']})"} for t in types
        ]
        context.user_data["from_type_map"] = {lbl["name"]: lbl["id"] for lbl in type_labels}
        await update.message.reply_text(
            "Select source account type",
            reply_markup=items_reply_keyboard(type_labels, ["Cancel"], columns=2),
        )
        return FROM_TYPE

    async def from_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        if text == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        type_map = context.user_data.get("from_type_map", {})
        if text not in type_map:
            await update.message.reply_text("Use provided buttons")
            return FROM_TYPE
        type_id = type_map[text]
        context.user_data["from_type"] = type_id
        user_id = update.effective_user.id
        groups = self.db.account_groups_with_value(user_id, type_id)
        group_labels = [
            {"id": g["id"], "name": f"{g['name']} ({g['value']})"} for g in groups
        ]
        context.user_data["from_group_map"] = {lbl["name"]: lbl["id"] for lbl in group_labels}
        await update.message.reply_text(
            "Select source account group",
            reply_markup=items_reply_keyboard(group_labels, ["Back", "Cancel"], columns=2),
        )
        return FROM_GROUP

    async def from_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        if text == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        if text == "Back":
            return await self.start_create_transaction(update, context)
        group_map = context.user_data.get("from_group_map", {})
        if text not in group_map:
            await update.message.reply_text("Use provided buttons")
            return FROM_GROUP
        group_id = group_map[text]
        context.user_data["from_group"] = group_id
        accounts = self.db.accounts_with_value(update.effective_user.id, group_id)
        acc_labels = [
            {"id": a["id"], "name": f"{a['name']} ({a['value']})"} for a in accounts
        ]
        row = self.db.fetchone(
            """
            SELECT t.name AS type_name
            FROM account_groups g
            JOIN account_types t ON g.type_id=t.id
            WHERE g.id=? AND g.user_id=?
            """,
            (group_id, update.effective_user.id),
        )
        extra = ["+ account", "Back", "Cancel"]
        if row and row["type_name"] == "capital":
            extra = ["Back", "Cancel"]
        context.user_data["from_account_map"] = {lbl["name"]: lbl["id"] for lbl in acc_labels}
        context.user_data["account_prefix"] = "from"
        await update.message.reply_text(
            "Select source account",
            reply_markup=items_reply_keyboard(acc_labels, extra, columns=2),
        )
        return FROM_ACCOUNT


    async def add_account_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text.strip()
        gid = context.user_data["add_group"]
        prefix = context.user_data["add_prefix"]
        user_id = update.effective_user.id
        if text == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        if text == "Back":
            accounts = self.db.accounts_with_value(user_id, gid)
            acc_labels = [{"id": a["id"], "name": f"{a['name']} ({a['value']})"} for a in accounts]
            acc_map_key = "from_account_map" if prefix == "from" else "to_account_map"
            context.user_data[acc_map_key] = {lbl["name"]: lbl["id"] for lbl in acc_labels}
            context.user_data["account_prefix"] = prefix
            await update.message.reply_text(
                "Select account",
                reply_markup=items_reply_keyboard(acc_labels, ["+ account", "Back", "Cancel"], columns=2),
            )
            return FROM_ACCOUNT if prefix == "from" else TO_ACCOUNT
        # prevent adding accounts inside capital type groups
        row = self.db.fetchone(
            """
            SELECT t.name AS type_name
            FROM account_groups g
            JOIN account_types t ON g.type_id=t.id
            WHERE g.id=? AND g.user_id=?
            """,
            (gid, user_id),
        )
        if row and row["type_name"] == "capital":
            accounts = self.db.accounts_with_value(user_id, gid)
            acc_labels = [
                {"id": a["id"], "name": f"{a['name']} ({a['value']})"} for a in accounts
            ]
            acc_map_key = "from_account_map" if prefix == "from" else "to_account_map"
            context.user_data[acc_map_key] = {lbl["name"]: lbl["id"] for lbl in acc_labels}
            context.user_data["account_prefix"] = prefix
            await update.message.reply_text(
                "Cannot create accounts in capital type",
                reply_markup=items_reply_keyboard(acc_labels, ["Back", "Cancel"], columns=2),
            )
            return FROM_ACCOUNT if prefix == "from" else TO_ACCOUNT

        name = text
        acc_id = self.db.add_account(user_id, gid, name)
        context.user_data["new_account_id"] = acc_id
        await update.message.reply_text("Enter initial value")
        return ADD_ACCOUNT_VALUE

    async def add_account_value(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text.strip()
        try:
            value = float(text)
        except ValueError:
            await update.message.reply_text("Please enter a number")
            return ADD_ACCOUNT_VALUE

        aid = context.user_data.pop("new_account_id")
        gid = context.user_data["add_group"]
        prefix = context.user_data["add_prefix"]
        user_id = update.effective_user.id

        if value != 0:
            row = self.db.fetchone(
                """
                SELECT g.name AS group_name, t.name AS type_name
                FROM account_groups g
                JOIN account_types t ON g.type_id=t.id
                WHERE g.id=? AND g.user_id=?
                """,
                (gid, user_id),
            )
            if row:
                gname = row["group_name"]
                tname = row["type_name"]
                if tname == "assets":
                    cap = self.db.fetchone(
                        """
                        SELECT a.id FROM accounts a
                        JOIN account_groups g ON a.group_id=g.id
                        JOIN account_types t ON g.type_id=t.id
                        WHERE a.user_id=? AND t.name='capital' AND g.name='assets' AND a.name=?
                        """,
                        (user_id, gname),
                    )
                    if cap:
                        self.db.add_transaction(user_id, cap["id"], aid, value)
                elif tname == "liabilities":
                    cap = self.db.fetchone(
                        """
                        SELECT a.id FROM accounts a
                        JOIN account_groups g ON a.group_id=g.id
                        JOIN account_types t ON g.type_id=t.id
                        WHERE a.user_id=? AND t.name='capital' AND g.name='liabilities' AND a.name=?
                        """,
                        (user_id, gname),
                    )
                    if cap:
                        self.db.add_transaction(user_id, aid, cap["id"], value)
                elif tname == "expenditures":
                    cap = self.db.fetchone(
                        """
                        SELECT a.id FROM accounts a
                        JOIN account_groups g ON a.group_id=g.id
                        JOIN account_types t ON g.type_id=t.id
                        WHERE a.user_id=? AND t.name='capital' AND g.name='expenditures' AND a.name=?
                        """,
                        (user_id, gname),
                    )
                    if cap:
                        self.db.add_transaction(user_id, cap["id"], aid, value)
                elif tname == "income":
                    cap = self.db.fetchone(
                        """
                        SELECT a.id FROM accounts a
                        JOIN account_groups g ON a.group_id=g.id
                        JOIN account_types t ON g.type_id=t.id
                        WHERE a.user_id=? AND t.name='capital' AND g.name='income' AND a.name=?
                        """,
                        (user_id, gname),
                    )
                    if cap:
                        self.db.add_transaction(user_id, aid, cap["id"], value)
                elif tname == "capital":
                    cap_id = self.db.correction_account(user_id)
                    self.db.add_transaction(user_id, aid, cap_id, value)

        accounts = self.db.accounts_with_value(user_id, gid)
        acc_labels = [
            {"id": a["id"], "name": f"{a['name']} ({a['value']})"} for a in accounts
        ]
        row = self.db.fetchone(
            """
            SELECT t.name AS type_name
            FROM account_groups g
            JOIN account_types t ON g.type_id=t.id
            WHERE g.id=? AND g.user_id=?
            """,
            (gid, user_id),
        )
        extra = ["+ account", "Back", "Cancel"]
        if row and row["type_name"] == "capital":
            extra = ["Back", "Cancel"]
        acc_map_key = "from_account_map" if prefix == "from" else "to_account_map"
        context.user_data[acc_map_key] = {lbl["name"]: lbl["id"] for lbl in acc_labels}
        context.user_data["account_prefix"] = prefix
        await update.message.reply_text(
            "Select account",
            reply_markup=items_reply_keyboard(acc_labels, extra, columns=2),
        )
        return FROM_ACCOUNT if prefix == "from" else TO_ACCOUNT

    async def from_account(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        if text == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        if text == "Back":
            user_id = update.effective_user.id
            groups = self.db.account_groups_with_value(
                user_id, context.user_data["from_type"]
            )
            group_labels = [
                {"id": g["id"], "name": f"{g['name']} ({g['value']})"} for g in groups
            ]
            context.user_data["from_group_map"] = {lbl["name"]: lbl["id"] for lbl in group_labels}
            await update.message.reply_text(
                "Select source account group",
                reply_markup=items_reply_keyboard(group_labels, ["Back", "Cancel"], columns=2),
            )
            return FROM_GROUP
        if text == "+ account":
            gid = context.user_data["from_group"]
            row = self.db.fetchone(
                """
                SELECT t.name AS type_name
                FROM account_groups g
                JOIN account_types t ON g.type_id=t.id
                WHERE g.id=? AND g.user_id=?
                """,
                (gid, update.effective_user.id),
            )
            if row and row["type_name"] == "capital":
                await update.message.reply_text("Cannot create accounts in capital type")
                return FROM_ACCOUNT
            context.user_data["add_prefix"] = context.user_data.get("account_prefix")
            context.user_data["add_group"] = gid
            await update.message.reply_text("Enter account name", reply_markup=ReplyKeyboardRemove())
            return ADD_ACCOUNT_NAME
        acc_map = context.user_data.get("from_account_map", {})
        if text not in acc_map:
            await update.message.reply_text("Use provided buttons")
            return FROM_ACCOUNT
        account_id = acc_map[text]
        context.user_data["from_account"] = account_id
        user_id = update.effective_user.id
        types = self.db.account_types_with_value(user_id)
        type_labels = [
            {"id": t["id"], "name": f"{t['name']} ({t['value']})"} for t in types
        ]
        context.user_data["to_type_map"] = {lbl["name"]: lbl["id"] for lbl in type_labels}
        await update.message.reply_text(
            "Select destination account type",
            reply_markup=items_reply_keyboard(type_labels, ["Back", "Cancel"], columns=2),
        )
        return TO_TYPE

    async def to_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        if text == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        if text == "Back":
            accounts = self.db.accounts_with_value(
                update.effective_user.id, context.user_data["from_group"]
            )
            acc_labels = [{"id": a["id"], "name": f"{a['name']} ({a['value']})"} for a in accounts]
            context.user_data["from_account_map"] = {lbl["name"]: lbl["id"] for lbl in acc_labels}
            context.user_data["account_prefix"] = "from"
            await update.message.reply_text(
                "Select source account",
                reply_markup=items_reply_keyboard(acc_labels, ["+ account", "Back", "Cancel"], columns=2),
            )
            return FROM_ACCOUNT
        type_map = context.user_data.get("to_type_map", {})
        if text not in type_map:
            await update.message.reply_text("Use provided buttons")
            return TO_TYPE
        type_id = type_map[text]
        context.user_data["to_type"] = type_id
        user_id = update.effective_user.id
        groups = self.db.account_groups_with_value(user_id, type_id)
        group_labels = [
            {"id": g["id"], "name": f"{g['name']} ({g['value']})"} for g in groups
        ]
        context.user_data["to_group_map"] = {lbl["name"]: lbl["id"] for lbl in group_labels}
        await update.message.reply_text(
            "Select destination account group",
            reply_markup=items_reply_keyboard(group_labels, ["Back", "Cancel"], columns=2),
        )
        return TO_GROUP

    async def to_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        if text == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        if text == "Back":
            user_id = update.effective_user.id
            types = self.db.account_types_with_value(user_id)
            type_labels = [
                {"id": t["id"], "name": f"{t['name']} ({t['value']})"} for t in types
            ]
            context.user_data["to_type_map"] = {lbl["name"]: lbl["id"] for lbl in type_labels}
            await update.message.reply_text(
                "Select destination account type",
                reply_markup=items_reply_keyboard(type_labels, ["Back", "Cancel"], columns=2),
            )
            return TO_TYPE
        group_map = context.user_data.get("to_group_map", {})
        if text not in group_map:
            await update.message.reply_text("Use provided buttons")
            return TO_GROUP
        group_id = group_map[text]
        context.user_data["to_group"] = group_id
        accounts = self.db.accounts_with_value(update.effective_user.id, group_id)
        acc_labels = [{"id": a["id"], "name": f"{a['name']} ({a['value']})"} for a in accounts]
        row = self.db.fetchone(
            """
            SELECT t.name AS type_name
            FROM account_groups g
            JOIN account_types t ON g.type_id=t.id
            WHERE g.id=? AND g.user_id=?
            """,
            (group_id, update.effective_user.id),
        )
        extra = ["+ account", "Back", "Cancel"]
        if row and row["type_name"] == "capital":
            extra = ["Back", "Cancel"]
        context.user_data["to_account_map"] = {lbl["name"]: lbl["id"] for lbl in acc_labels}
        context.user_data["account_prefix"] = "to"
        await update.message.reply_text(
            "Select destination account",
            reply_markup=items_reply_keyboard(acc_labels, extra, columns=2),
        )
        return TO_ACCOUNT

    async def to_account(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        if text == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        if text == "Back":
            user_id = update.effective_user.id
            groups = self.db.account_groups_with_value(
                user_id, context.user_data["to_type"]
            )
            group_labels = [
                {"id": g["id"], "name": f"{g['name']} ({g['value']})"} for g in groups
            ]
            context.user_data["to_group_map"] = {lbl["name"]: lbl["id"] for lbl in group_labels}
            await update.message.reply_text(
                "Select destination account group",
                reply_markup=items_reply_keyboard(group_labels, ["Back", "Cancel"], columns=2),
            )
            return TO_GROUP
        if text == "+ account":
            gid = context.user_data["to_group"]
            row = self.db.fetchone(
                """
                SELECT t.name AS type_name
                FROM account_groups g
                JOIN account_types t ON g.type_id=t.id
                WHERE g.id=? AND g.user_id=?
                """,
                (gid, update.effective_user.id),
            )
            if row and row["type_name"] == "capital":
                await update.message.reply_text("Cannot create accounts in capital type")
                return TO_ACCOUNT
            context.user_data["add_prefix"] = context.user_data.get("account_prefix")
            context.user_data["add_group"] = gid
            await update.message.reply_text("Enter account name", reply_markup=ReplyKeyboardRemove())
            return ADD_ACCOUNT_NAME
        acc_map = context.user_data.get("to_account_map", {})
        if text not in acc_map:
            await update.message.reply_text("Use provided buttons")
            return TO_ACCOUNT
        account_id = acc_map[text]
        context.user_data["to_account"] = account_id
        await update.message.reply_text(
            "Enter amount",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("Back"), KeyboardButton("Cancel")]],
                resize_keyboard=True,
            ),
        )
        context.user_data.pop("editing", None)
        return AMOUNT

    async def amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        if text == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        if text == "Back":
            accounts = self.db.accounts_with_value(
                update.effective_user.id, context.user_data["to_group"]
            )
            acc_labels = [{"id": a["id"], "name": f"{a['name']} ({a['value']})"} for a in accounts]
            context.user_data["to_account_map"] = {lbl["name"]: lbl["id"] for lbl in acc_labels}
            context.user_data["account_prefix"] = "to"
            await update.message.reply_text(
                "Select destination account",
                reply_markup=items_reply_keyboard(acc_labels, ["+ account", "Back", "Cancel"], columns=2),
            )
            return TO_ACCOUNT
        try:
            amount = float(text)
        except ValueError:
            await update.message.reply_text("Please enter a number")
            return AMOUNT
        user_id = update.effective_user.id
        if context.user_data.get("editing"):
            tx_id = context.user_data["tx_id"]
            self.db.update_transaction_amount(user_id, tx_id, amount)
            tx = self.db.transaction(user_id, tx_id)
            await update.message.reply_text(
                f"{tx['from_name']} - {tx['amount']} -> {tx['to_name']}"
            )
            await update.message.reply_text(
                "Transaction saved", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        context.user_data["amount"] = amount
        await update.message.reply_text(
            "Enter date and time (YYYY-MM-DD HH:MM) or 'Now'",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("Now"), KeyboardButton("Back"), KeyboardButton("Cancel")]],
                resize_keyboard=True,
            ),
        )
        return TX_DATETIME

    async def tx_datetime(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text.strip()
        if text == "Cancel":
            await update.message.reply_text(
                "Cancelled", reply_markup=self.main_menu_keyboard()
            )
            return ConversationHandler.END
        if text == "Back":
            await update.message.reply_text(
                "Enter amount",
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton("Back"), KeyboardButton("Cancel")]],
                    resize_keyboard=True,
                ),
            )
            return AMOUNT
        if text.lower() == "now":
            ts = None
        else:
            try:
                from datetime import datetime
                dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
                ts = dt.isoformat(sep=" ")
            except ValueError:
                await update.message.reply_text(
                    "Please use format YYYY-MM-DD HH:MM or 'Now'"
                )
                return TX_DATETIME
        user_id = update.effective_user.id
        tx_id = self.db.add_transaction(
            user_id,
            context.user_data["from_account"],
            context.user_data["to_account"],
            context.user_data["amount"],
            ts,
        )
        tx = self.db.transaction(user_id, tx_id)
        await update.message.reply_text(
            f"{tx['from_name']} - {tx['amount']} -> {tx['to_name']}"
        )
        await update.message.reply_text(
            "Transaction saved", reply_markup=self.main_menu_keyboard()
        )
        return ConversationHandler.END

