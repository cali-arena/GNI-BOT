#!/usr/bin/env sh
# Verify WhatsApp QR flow end-to-end
# Usage: WA_QR_BRIDGE_TOKEN=your-token sh scripts/verify_wa.sh
#        Or set WA_QR_BRIDGE_TOKEN in .env file (will be loaded automatically)
#
# Required env vars:
#   WA_QR_BRIDGE_TOKEN - Bearer token for Authorization header (required)
#   BASE_URL - API base URL (default: http://localhost:8000)

# POSIX-compatible script - uses sh, not bash

# Load .env if present (POSIX-compatible)
if [ -f .env ]; then
    # Read .env file line by line, skipping comments and empty lines
    while IFS= read -r line || [ -n "$line" ]; do
        # Skip comments and empty lines
        case "$line" in
            \#*|'') continue ;;
        esac
        # Export variable (POSIX-compatible)
        export "$line" 2>/dev/null || true
    done < .env
fi

WA_QR_BRIDGE_TOKEN="${WA_QR_BRIDGE_TOKEN:-}"
if [ -z "$WA_QR_BRIDGE_TOKEN" ]; then
    echo "ERROR: WA_QR_BRIDGE_TOKEN environment variable not set" >&2
    echo "Usage: WA_QR_BRIDGE_TOKEN=your-token sh scripts/verify_wa.sh" >&2
    echo "       Or set WA_QR_BRIDGE_TOKEN in .env file" >&2
    exit 1
fi

BASE_URL="${BASE_URL:-http://localhost:8000}"

echo "=== WhatsApp QR Flow Verification ==="
echo "API URL: $BASE_URL"
echo ""

# 1. Trigger reconnect
echo "Triggering reconnect..."
RECONNECT_RESPONSE=$(curl -sS -w "\n%{http_code}" -X POST \
    -H "Authorization: Bearer $WA_QR_BRIDGE_TOKEN" \
    "$BASE_URL/admin/wa/reconnect" 2>/dev/null || printf "\n000")
RECONNECT_HTTP_CODE=$(echo "$RECONNECT_RESPONSE" | tail -n1)
RECONNECT_BODY=$(echo "$RECONNECT_RESPONSE" | sed '$d')

if [ "$RECONNECT_HTTP_CODE" != "200" ]; then
    echo "ERROR: Reconnect failed (HTTP $RECONNECT_HTTP_CODE)" >&2
    echo "$RECONNECT_BODY" >&2
    exit 1
fi

echo "✓ Reconnect triggered"
echo ""

# 2. Poll /admin/wa/qr every 2 seconds for max 60 seconds
echo "Polling for QR code (every 2s, max 60s)..."
MAX_WAIT=60
ELAPSED=0
INTERVAL=2
QR_FOUND=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    # Fetch QR status
    QR_RESPONSE=$(curl -sS -w "\n%{http_code}" \
        -H "Authorization: Bearer $WA_QR_BRIDGE_TOKEN" \
        "$BASE_URL/admin/wa/qr" 2>/dev/null || printf "\n000")
    QR_HTTP_CODE=$(echo "$QR_RESPONSE" | tail -n1)
    QR_BODY=$(echo "$QR_RESPONSE" | sed '$d')
    
    if [ "$QR_HTTP_CODE" != "200" ]; then
        echo "ERROR: QR endpoint failed (HTTP $QR_HTTP_CODE)" >&2
        echo "$QR_BODY" >&2
        exit 1
    fi
    
    # Parse status and QR code using jq
    QR_STATUS=$(echo "$QR_BODY" | jq -r '.status // "unknown"' 2>/dev/null || echo "unknown")
    QR_CODE=$(echo "$QR_BODY" | jq -r '.qr // empty' 2>/dev/null || echo "")
    
    # Print current status (no secrets printed)
    echo "[${ELAPSED}s] Status: $QR_STATUS"
    
    # Check if QR is ready
    if [ "$QR_STATUS" = "qr_ready" ] && [ -n "$QR_CODE" ] && [ "$QR_CODE" != "null" ] && [ "$QR_CODE" != "" ]; then
        echo ""
        echo "✓ QR code ready!"
        # Print first 120 chars of QR (no secrets - QR is not a secret)
        QR_PREVIEW=$(echo "$QR_CODE" | cut -c 1-120)
        echo "QR (first 120 chars): $QR_PREVIEW"
        QR_FOUND=1
        break
    elif [ "$QR_STATUS" = "connected" ]; then
        echo ""
        echo "✓ Bot already connected (no QR needed)"
        QR_FOUND=1
        break
    fi
    
    # Wait before next poll
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
done

# Final result
if [ $QR_FOUND -eq 0 ]; then
    echo ""
    echo "✗ Timeout: QR not generated after ${MAX_WAIT}s" >&2
    echo "Final status:" >&2
    FINAL_RESPONSE=$(curl -sS \
        -H "Authorization: Bearer $WA_QR_BRIDGE_TOKEN" \
        "$BASE_URL/admin/wa/qr" 2>/dev/null || echo "error")
    echo "$FINAL_RESPONSE" | jq '.' 2>/dev/null || echo "$FINAL_RESPONSE" >&2
    exit 1
fi

echo ""
echo "=== Verification Complete ==="
exit 0
