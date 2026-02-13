#!/usr/bin/env bash
# Install systemd service for auto-starting Docker Compose on VM reboot.
# Usage: sudo bash scripts/install_systemd_service.sh
#
# This creates /etc/systemd/system/gni-bot.service that runs:
#   docker compose up -d
# on boot.

set -e

if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run as root (use sudo)" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Detect user who owns the repo (for docker compose)
REPO_OWNER=$(stat -c '%U' "$REPO_ROOT" 2>/dev/null || stat -f '%Su' "$REPO_ROOT" 2>/dev/null || echo "$SUDO_USER")

echo "=== Installing systemd service for GNI Bot Creator ==="
echo "Repository: $REPO_ROOT"
echo "Owner: $REPO_OWNER"
echo ""

# Create systemd service file
SERVICE_FILE="/etc/systemd/system/gni-bot.service"
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=GNI Bot Creator Docker Compose Stack
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$REPO_ROOT
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
User=$REPO_OWNER
Group=$REPO_OWNER

# Restart policy
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "Created service file: $SERVICE_FILE"
echo ""

# Reload systemd
systemctl daemon-reload

# Enable service (start on boot)
systemctl enable gni-bot.service

echo "✓ Service installed and enabled"
echo ""
echo "To start service now:"
echo "  sudo systemctl start gni-bot"
echo ""
echo "To check status:"
echo "  sudo systemctl status gni-bot"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u gni-bot -f"
echo ""
echo "To disable auto-start:"
echo "  sudo systemctl disable gni-bot"
