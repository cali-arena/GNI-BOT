#!/usr/bin/env bash
# Provision Ubuntu VM: Docker install, UFW baseline, optional swap.
# Run as root or with sudo. Usage: ./scripts/provision_ubuntu.sh [--swap SIZE_MB]

set -e

SWAP_MB=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --swap)
      SWAP_MB="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

# Docker install (Ubuntu)
apt-get update
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${VERSION_CODENAME:-$UBUNTU_CODENAME}") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# UFW baseline: allow SSH, HTTP, HTTPS; default deny
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable || true

# Optional swap
if [[ -n "$SWAP_MB" ]] && [[ "$SWAP_MB" =~ ^[0-9]+$ ]]; then
  SWAP_FILE=/swapfile
  if [[ ! -f $SWAP_FILE ]]; then
    fallocate -l "${SWAP_MB}M" $SWAP_FILE
    chmod 600 $SWAP_FILE
    mkswap $SWAP_FILE
    swapon $SWAP_FILE
    echo "$SWAP_FILE none swap sw 0 0" >> /etc/fstab
  fi
fi

echo "Provision done. Docker: $(docker --version). UFW status: $(ufw status 2>/dev/null | head -1)."
