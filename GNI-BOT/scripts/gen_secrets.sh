#!/usr/bin/env sh
# Generate production secrets for VM deployment. Copy-paste the output into .env.
# Requires: openssl (for random bytes). No Python/Node required.

set -e

# 32 bytes = 64 hex chars for passwords/tokens
_hex() { openssl rand -hex 32; }

POSTGRES_PASSWORD="$(_hex)"
JWT_SECRET="$(_hex)"
API_KEY="$(_hex)"
WA_QR_BRIDGE_TOKEN="$(_hex)"

echo "# Generated secrets — copy into .env (do not commit)"
echo "POSTGRES_PASSWORD=$POSTGRES_PASSWORD"
echo "JWT_SECRET=$JWT_SECRET"
echo "API_KEY=$API_KEY"
echo "ADMIN_API_KEY=$API_KEY"
echo "WA_QR_BRIDGE_TOKEN=$WA_QR_BRIDGE_TOKEN"
