#!/usr/bin/env bash
# Open port 8000 so Streamlit Cloud (and other clients) can reach your API.
# Run on the VM: sudo bash scripts/open_port_8000.sh

set -e

echo "=== Open port 8000 for API (Streamlit Cloud login) ==="

# 1) UFW (Ubuntu/Debian)
if command -v ufw &>/dev/null; then
    echo "Using ufw..."
    if sudo ufw status | grep -q "8000.*ALLOW"; then
        echo "  Port 8000 already allowed."
    else
        sudo ufw allow 8000/tcp
        echo "  Port 8000 allowed. Reloading..."
        sudo ufw reload
        echo "  Done."
    fi
    sudo ufw status | grep 8000 || true
    echo ""
fi

# 2) iptables (if no ufw)
if ! command -v ufw &>/dev/null; then
    echo "ufw not found. If you use iptables, allow 8000 manually:"
    echo "  iptables -I INPUT -p tcp --dport 8000 -j ACCEPT"
    echo ""
fi

echo "Also check your cloud provider's firewall / security group:"
echo "  - Hetzner: Firewall rules for this server → allow inbound TCP 8000"
echo "  - AWS/GCP/Azure: Security group / VPC firewall → allow inbound TCP 8000"
echo ""
echo "Test from outside the VM (e.g. your PC):"
echo "  curl -s http://YOUR_VM_IP:8000/health"
echo "  (Replace YOUR_VM_IP with 217.216.84.81 or your server's public IP)"
echo ""
