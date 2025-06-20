#!/bin/bash
# Script to deploy and run the bot as a systemd service

set -e

APP_DIR=$(dirname $(readlink -f "$0"))
VENV="$APP_DIR/venv"
PYTHON="$VENV/bin/python"

if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
fi

"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r "$APP_DIR/requirements.txt"

SERVICE_FILE="/etc/systemd/system/freemoney.service"

echo "[Unit]" | sudo tee "$SERVICE_FILE" > /dev/null
sudo tee -a "$SERVICE_FILE" > /dev/null <<EOF2
Description=FreeMoney Telegram Bot
After=network.target

[Service]
WorkingDirectory=$APP_DIR
ExecStart=$PYTHON $APP_DIR/bot-start-freemoney.py
Restart=always
EnvironmentFile=$APP_DIR/.env

[Install]
WantedBy=multi-user.target
EOF2

sudo systemctl daemon-reload
sudo systemctl enable freemoney.service
sudo systemctl restart freemoney.service
