# ForeMoney Telegram Bot

This project contains a simple Telegram bot for managing personal finance using a double-entry accounting approach. The bot is designed with modular structure and prepared for further development.

## Features

- Basic Telegram bot skeleton with main menu.
- SQLite database with tables for accounts, account groups, account types and transactions.
- `.env` configuration using `python-dotenv`.
- `deploy.sh` script installs dependencies in a virtual environment and configures a systemd service.

## Setup

1. Copy `.env.example` to `.env` and fill in your `TELEGRAM_TOKEN`.
2. Run `python3 -m venv venv && source venv/bin/activate`.
3. Install dependencies with `pip install -r requirements.txt`.
4. Start the bot using `python bot-start-foremoney.py`.

To deploy as a service on a server, use `./deploy.sh` with appropriate permissions.
