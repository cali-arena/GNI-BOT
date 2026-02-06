#!/usr/bin/env bash
# Install systemd unit gni-bot.service for 24/7 VM uptime.
# Run on VM with sudo. Usage: sudo bash scripts/install_systemd.sh
# Override: APP_DIR=/opt/gni-bot-creator sudo bash scripts/install_systemd.sh
set -e

APP_DIR="${APP_DIR:-/opt/gni-bot-creator}"
UNIT_FILE=/etc/systemd/system/gni-bot.service

echo "=== GNI Bot — systemd install ==="
echo "  WorkingDirectory: ${APP_DIR}"
echo "  Unit file: ${UNIT_FILE}"
echo ""

if [ ! -d "$APP_DIR" ]; then
  echo "  FAIL: WorkingDirectory ${APP_DIR} does not exist."
  exit 1
fi

cat > "$UNIT_FILE" << EOF
[Unit]
Description=GNI Bot Creator (Docker Compose)
After=docker.service network-online.target
Wants=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${APP_DIR}
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
Restart=always
RestartSec=5
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
EOF

echo "Wrote ${UNIT_FILE}"
systemctl daemon-reload
systemctl enable gni-bot
systemctl restart gni-bot

echo ""
echo "=== Installed ==="
echo "  Status: sudo systemctl status gni-bot"
echo "  Logs:   sudo journalctl -u gni-bot -f"
echo "  Stop:   sudo systemctl stop gni-bot"
echo ""
