#!/usr/bin/env bash
# Fix gni-bot.service "bad unit file" on VM. Run once: sudo bash fix_systemd_vm.sh
# Use from any directory; sets WorkingDirectory=/opt/gni.
set -e
UNIT_FILE=/etc/systemd/system/gni-bot.service
APP_DIR=/opt/gni

echo "Fixing ${UNIT_FILE} for ${APP_DIR}..."

sudo tee "$UNIT_FILE" > /dev/null << EOF
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
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable gni-bot
sudo systemctl start gni-bot
echo "Done. Check: sudo systemctl status gni-bot"
sudo systemctl status gni-bot --no-pager
