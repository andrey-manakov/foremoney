from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from .config import get_settings
from .database import Database
from .states import *  # noqa: F401,F403
from .menu import MenuMixin
from .dashboard import DashboardMixin
from .transactions import TransactionCreateMixin, TransactionListMixin
from .settings_dashboard import SettingsDashboardMixin
from .settings_groups import SettingsGroupsMixin
from .settings_accounts import SettingsAccountsMixin


class FinanceBot(
    TransactionCreateMixin,
    TransactionListMixin,
    DashboardMixin,
    SettingsDashboardMixin,
    SettingsGroupsMixin,
    SettingsAccountsMixin,
    MenuMixin,
):
    def __init__(self) -> None:
        self.settings = get_settings()
        self.db = Database(self.settings.database_path)

    def build_app(self) -> Application:
        application = Application.builder().token(self.settings.token).build()
        application.add_handler(CommandHandler("start", self.start))

        create_tx_conv = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex("^Create transaction$"), self.start_create_transaction)],
            states={
                FROM_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.from_type)],
                FROM_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.from_group)],
                FROM_ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.from_account)],
                TO_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.to_type)],
                TO_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.to_group)],
                TO_ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.to_account)],
                AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.amount)],
                TX_DATETIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.tx_datetime)],
                ADD_ACCOUNT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_account_name)],
                ADD_ACCOUNT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_account_value)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
            allow_reentry=True,
        )
        application.add_handler(create_tx_conv)

        tx_conv = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex("^Transactions$"), self.start_transactions)],
            states={
                TX_LIST: [CallbackQueryHandler(self.tx_list_actions)],
                TX_DETAILS: [CallbackQueryHandler(self.tx_details_action)],
                TX_EDIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.tx_edit_amount)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
            allow_reentry=True,
        )
        application.add_handler(tx_conv)

        dashboard_conv = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex("^Dashboard$"), self.start_dashboard)],
            states={
                DASH_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dashboard_menu)],
                DASH_ACC_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dashboard_acc_type)],
                DASH_ACC_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dashboard_acc_menu)],
                DASH_GROUP_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dashboard_group_select)],
                DASH_GROUP_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dashboard_group_menu)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )
        application.add_handler(dashboard_conv)

        settings_conv = ConversationHandler(
            entry_points=[
                MessageHandler(filters.Regex("^Settings$"), self.start_settings),
                CallbackQueryHandler(self.start_settings, pattern="^opensettings$"),
            ],
            states={
                SETTINGS_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.settings_menu)],
                DASHBOARD_ACCOUNTS: [
                    CallbackQueryHandler(self.toggle_dashboard_account, pattern="^dashacc:"),
                    CallbackQueryHandler(self.save_dashboard_accounts, pattern="^dashsave$"),
                    CallbackQueryHandler(self.cancel_settings_submenu, pattern="^dashcancel$"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.settings_menu),
                ],
                AG_TYPE_SELECT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.ag_type_selected)
                ],
                AG_GROUPS: [
                    MessageHandler(filters.Regex("^\\+ group$"), self.ag_add_group_prompt),
                    MessageHandler(filters.Regex("^Back$"), self.ag_type_back),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.ag_select_group),
                ],
                AG_ADD_GROUP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.ag_add_group_name)],
                AG_ACCOUNTS: [
                    MessageHandler(filters.Regex("^\\+ account$"), self.acc_add_prompt),
                    MessageHandler(filters.Regex("^Rename group$"), self.grename_prompt),
                    MessageHandler(filters.Regex("^Delete group$"), self.gdelete),
                    MessageHandler(filters.Regex("^Back$"), self.groups_back),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.acc_select),
                ],
                AG_GROUP_RENAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.grename)],
                AG_ADD_ACCOUNT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.acc_add_name)],
                AG_ADD_ACCOUNT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.acc_add_value)],
                ACCOUNT_MENU: [
                    MessageHandler(filters.Regex("^Rename$"), self.account_rename_prompt),
                    MessageHandler(filters.Regex("^Delete$"), self.account_delete),
                    MessageHandler(filters.Regex("^Back$"), self.account_menu_back),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.account_menu_back),
                ],
                ACCOUNT_RENAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.account_rename)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )
        application.add_handler(settings_conv)

        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_menu)
        )
        return application


def main() -> None:
    bot = FinanceBot()
    app = bot.build_app()
    app.run_polling()


if __name__ == "__main__":
    main()
