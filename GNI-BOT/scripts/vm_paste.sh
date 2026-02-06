#!/bin/bash
# Run on VM:  curl -sSf https://raw.githubusercontent.com/.../vm_paste.sh | bash
# Or copy-paste the block below into the VM terminal.

set -e
cd /opt/gni || { echo "Create /opt/gni and put GNI-BOT there (or set APP_DIR)"; exit 1; }
git pull origin main 2>/dev/null || true
test -f .env || cp .env.example .env
docker compose build
docker compose up -d
docker compose --profile qr-ui up -d
docker compose ps
echo "Done. API: http://$(hostname -I | awk '{print $1}'):8000  QR UI: http://$(hostname -I | awk '{print $1}'):8501"
