# ForeMoney Telegram Bot

ForeMoney is a Telegram bot that helps you manage personal finances using a
double-entry accounting approach. The code base is modular and already
implements transaction management, dashboard charts and a settings section.

## Features

- Main menu with access to Dashboard, Settings and Transactions.
- Wizard for creating transactions between accounts.
- Transaction listing with the ability to edit or delete entries.
- Dashboard that displays account balances and charts using `matplotlib`.
- Settings section for managing account groups, individual accounts and
  selecting which accounts appear on the dashboard.
- SQLite database for storing all data. The database structure is created
  automatically and can be recreated from the Settings menu.
- Data export/import of the entire database via a zipped collection of CSV files.
- `.env` configuration using `python-dotenv`.
- `deploy.sh` script installs dependencies in a virtual environment and
  configures a systemd service.

## Setup

1. Copy `.env.example` to `.env` and fill in your `TELEGRAM_TOKEN`.
   You can also change `DATABASE_PATH` to specify where the SQLite database
   will be created.
2. Run `python3 -m venv venv && source venv/bin/activate`.
3. Install dependencies with `pip install -r requirements.txt`.
4. Start the bot using `python bot-start-foremoney.py`.

To deploy as a service on a server, use `./deploy.sh` with appropriate permissions.

## Code overview

The project is organised into small modules which provide different bot
features:

- **bot-start-foremoney.py** – simple entry point that creates and runs the bot.
- **deploy.sh** – helper script that installs dependencies and sets up a
  systemd service.
- **foremoney/bot.py** – main `FinanceBot` class combining all mixins and
  registering conversation handlers.
- **foremoney/config.py** – loads environment variables and returns `Settings`.
- **foremoney/constants.py** – default account types and groups used when
  seeding the database.
- **foremoney/database.py** – lightweight wrapper over SQLite with helper
  methods for accounts, transactions and settings.
- **foremoney/init_data.py** – populates initial account types, groups and
  capital accounts for a user.
- **foremoney/menu.py** – handlers for the main menu commands.
- **foremoney/dashboard.py** – dashboard views displaying balances and charts.
- **foremoney/settings_dashboard.py** – settings for dashboard accounts and
  database maintenance.
- **foremoney/settings_groups.py** – manage account groups and their accounts.
- **foremoney/settings_accounts.py** – operations on individual accounts.
- **foremoney/states.py** – numeric constants describing all conversation
  states.
- **foremoney/ui.py** – small utility helpers for generating keyboard layouts.
- **foremoney/transactions/** – transaction creation and listing logic:
  - `create.py` – step by step wizard to create a transaction.
  - `list.py` – list, edit and delete transactions.
  - `helpers.py` – shared helper functions.
