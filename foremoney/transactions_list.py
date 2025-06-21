from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from .states import TX_LIST, TX_DETAILS, TX_EDIT_AMOUNT

class TransactionListMixin:
    """Handlers for listing and editing transactions."""

    async def start_transactions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        return await self._send_transactions(update.message, update.effective_user.id, 0)

    async def _send_transactions(self, sender, user_id: int, offset: int) -> int:
        msg_obj = sender if hasattr(sender, "reply_text") else sender.message
        txs = self.db.transactions(user_id, 10, offset)
        buttons = [
            [InlineKeyboardButton(
                f"{tx['from_name']} - {tx['amount']} -> {tx['to_name']}",
                callback_data=f"tx:{tx['id']}"
            )]
            for tx in txs
        ]
        if txs:
            buttons.append([InlineKeyboardButton("Next", callback_data="next")])
        await msg_obj.reply_text(
            "Transactions:",
            reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
        )
        return TX_LIST

    async def tx_list_actions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        if query.data == "next":
            offset = context.user_data.get("tx_offset", 0) + 10
            context.user_data["tx_offset"] = offset
            await query.message.delete()
            return await self._send_transactions(query.message, user_id, offset)
        if query.data.startswith("tx:"):
            tx_id = int(query.data.split(":")[1])
            tx = self.db.transaction(user_id, tx_id)
            if not tx:
                await query.message.reply_text("Transaction not found")
                return TX_LIST
            context.user_data["tx_id"] = tx_id
            await query.message.reply_text(
                f"{tx['from_name']} - {tx['amount']} -> {tx['to_name']}",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("Edit", callback_data="edit")],
                        [InlineKeyboardButton("Delete", callback_data="delete")],
                    ]
                ),
            )
            return TX_DETAILS
        return TX_LIST

    async def tx_details_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        tx_id = context.user_data.get("tx_id")
        if query.data == "delete" and tx_id:
            self.db.delete_transaction(user_id, tx_id)
            await query.message.reply_text("Transaction deleted")
            return ConversationHandler.END
        if query.data == "edit" and tx_id:
            context.user_data["editing_tx"] = True
            await query.message.reply_text("Enter new amount")
            return TX_EDIT_AMOUNT
        return TX_DETAILS

    async def tx_edit_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            amount = float(update.message.text)
        except ValueError:
            await update.message.reply_text("Please enter a number")
            return TX_EDIT_AMOUNT
        user_id = update.effective_user.id
        tx_id = context.user_data.get("tx_id")
        if tx_id:
            self.db.update_transaction_amount(user_id, tx_id, amount)
            tx = self.db.transaction(user_id, tx_id)
            await update.message.reply_text(
                f"{tx['from_name']} - {tx['amount']} -> {tx['to_name']}",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("Edit", callback_data="edit")],
                        [InlineKeyboardButton("Delete", callback_data="delete")],
                    ]
                ),
            )
            return TX_DETAILS
        return ConversationHandler.END
