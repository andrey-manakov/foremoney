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
from .transactions_create import TransactionCreateMixin
from .transactions_list import TransactionListMixin
from .settings_dashboard import SettingsDashboardMixin
from .settings_groups import SettingsGroupsMixin
from .settings_accounts import SettingsAccountsMixin


class FinanceBot(
    TransactionCreateMixin,
    TransactionListMixin,
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
                FROM_TYPE: [CallbackQueryHandler(self.from_type, pattern="^ftype:")],
                FROM_GROUP: [
                    CallbackQueryHandler(self.from_group, pattern="^fgroup:"),
                    CallbackQueryHandler(self.add_account_prompt, pattern="^addacc:from:"),
                ],
                FROM_ACCOUNT: [
                    CallbackQueryHandler(self.from_account, pattern="^facc:"),
                    CallbackQueryHandler(self.add_account_prompt, pattern="^addacc:from:"),
                ],
                TO_TYPE: [CallbackQueryHandler(self.to_type, pattern="^ttype:")],
                TO_GROUP: [
                    CallbackQueryHandler(self.to_group, pattern="^tgroup:"),
                    CallbackQueryHandler(self.add_account_prompt, pattern="^addacc:to:"),
                ],
                TO_ACCOUNT: [
                    CallbackQueryHandler(self.to_account, pattern="^tacc:"),
                    CallbackQueryHandler(self.add_account_prompt, pattern="^addacc:to:"),
                ],
                AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.amount)],
                ADD_ACCOUNT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_account_name)],
                SUMMARY: [CallbackQueryHandler(self.summary_action, pattern="^(edit|delete)$")],
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
        )
        application.add_handler(tx_conv)

        settings_conv = ConversationHandler(
            entry_points=[
                MessageHandler(filters.Regex("^Settings$"), self.start_settings),
                CallbackQueryHandler(self.start_settings, pattern="^opensettings$"),
            ],
            states={
                SETTINGS_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.settings_menu)],
                DASHBOARD_ACCOUNTS: [
                    CallbackQueryHandler(self.toggle_dashboard_account, pattern="^dashacc:"),
                    CallbackQueryHandler(self.save_dashboard_accounts, pattern="^dashsave$")
                ],
                AG_TYPE_SELECT: [CallbackQueryHandler(self.ag_type_selected, pattern="^agtype:")],
                AG_GROUPS: [
                    CallbackQueryHandler(self.ag_select_group, pattern="^aggroup:"),
                    CallbackQueryHandler(self.ag_add_group_prompt, pattern="^agaddgroup$"),
                    CallbackQueryHandler(self.ag_type_back, pattern="^agtypeback$")
                ],
                AG_ADD_GROUP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.ag_add_group_name)],
                AG_ACCOUNTS: [
                    CallbackQueryHandler(self.acc_select, pattern="^acc:"),
                    CallbackQueryHandler(self.acc_add_prompt, pattern="^addacc$"),
                    CallbackQueryHandler(self.grename_prompt, pattern="^grename$"),
                    CallbackQueryHandler(self.gdelete, pattern="^gdelete$"),
                    CallbackQueryHandler(self.groups_back, pattern="^groupsback$")
                ],
                AG_GROUP_RENAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.grename)],
                AG_ADD_ACCOUNT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.acc_add_name)],
                ACCOUNT_MENU: [
                    CallbackQueryHandler(self.account_rename_prompt, pattern="^renacc$"),
                    CallbackQueryHandler(self.account_delete, pattern="^delacc$"),
                    CallbackQueryHandler(self.account_menu_back, pattern="^accback$")
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
