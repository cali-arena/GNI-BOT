#!/usr/bin/env bash
# Verify WhatsApp QR flow: status, connect, poll for QR until qr_ready (max 90s).
# Requires: WA_QR_BRIDGE_TOKEN. Optional: API_URL (default http://127.0.0.1:8000).
# Usage: from repo root, source .env; ./scripts/verify_wa_flow.sh
set -e

cd "$(dirname "$0")/.."
[ -f .env ] && set -a && source .env 2>/dev/null && set +a || true

API_URL="${API_URL:-http://127.0.0.1:8000}"
TOKEN="${WA_QR_BRIDGE_TOKEN:-}"

if [ -z "$TOKEN" ]; then
  echo "Missing WA_QR_BRIDGE_TOKEN. Set in .env or export."
  exit 1
fi

CURL_AUTH=(-H "Authorization: Bearer $TOKEN")

echo "=== WhatsApp QR flow verification ==="
echo "API_URL=$API_URL"

echo "1. GET /wa/status..."
if ! curl -sf "${CURL_AUTH[@]}" "$API_URL/wa/status" >/dev/null; then
  echo "FAIL: /wa/status unreachable"
  exit 1
fi
echo "   OK"

echo "2. POST /wa/connect..."
if ! curl -sf -X POST "${CURL_AUTH[@]}" "$API_URL/wa/connect" >/dev/null; then
  echo "FAIL: /wa/connect failed"
  exit 1
fi
echo "   OK"

echo "3. Polling /wa/qr for up to 90s..."
max=90
interval=5
elapsed=0
while [ $elapsed -lt $max ]; do
  resp=$(curl -sf "${CURL_AUTH[@]}" "$API_URL/wa/qr" 2>/dev/null || echo "{}")
  ready=$(echo "$resp" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    s = d.get('status', '')
    q = d.get('qr') or ''
    print('ok' if s == 'qr_ready' or q else '')
except: print('')
" 2>/dev/null || echo "")

  if [ "$ready" = "ok" ]; then
    echo "   QR ready"
    echo "=== Success ==="
    exit 0
  fi
  sleep $interval
  elapsed=$((elapsed + interval))
  echo "   ... waiting (${elapsed}s)"
done

echo "FAIL: QR not ready after ${max}s"
exit 1
