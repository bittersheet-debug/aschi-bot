#!/bin/bash
# ==============================================================================
# ASCHI BOT — AUTOMATED 24/7 VPS DEPLOYMENT SCRIPT (UBUNTU / DEBIAN)
# ASCHEN EVENT ORGANIZER
# ==============================================================================

set -e

echo "=== Memperbarui package system ==="
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv git curl

INSTALL_DIR="/opt/aschi-bot"
echo "=== Menyiapkan direktori di $INSTALL_DIR ==="
sudo mkdir -p $INSTALL_DIR
sudo cp -r ./* $INSTALL_DIR/
cd $INSTALL_DIR

echo "=== Menyiapkan Virtual Environment Python ==="
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo "=== Memasang Systemd Service (Auto-Start & 24/7 Keep-Alive) ==="
sudo cp aschi-bot.service /etc/systemd/system/aschi-bot.service
sudo systemctl daemon-reload
sudo systemctl enable aschi-bot
sudo systemctl restart aschi-bot

echo "=== Status Service ==="
sudo systemctl status aschi-bot --no-pager

echo ""
echo "=========================================================="
echo " [BERHASIL] ASCHI BOT AKTIF 24 JAM DI SERVER VPS!"
echo " Cek log realtime: sudo journalctl -u aschi-bot -f"
echo " Restart bot:      sudo systemctl restart aschi-bot"
echo " Stop bot:         sudo systemctl stop aschi-bot"
echo "=========================================================="
