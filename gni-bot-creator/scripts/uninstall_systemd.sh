#!/usr/bin/env bash
# Uninstall systemd unit gni-bot.service.
# Run on VM with sudo. Usage: sudo bash scripts/uninstall_systemd.sh
set -e

UNIT_FILE=/etc/systemd/system/gni-bot.service

echo "=== GNI Bot — systemd uninstall ==="

systemctl stop gni-bot 2>/dev/null || true
systemctl disable gni-bot 2>/dev/null || true
rm -f "$UNIT_FILE"
systemctl daemon-reload

echo "Removed ${UNIT_FILE}"
echo "Stack stopped and disabled. Containers may still be running; run 'docker compose down' in app dir if needed."
