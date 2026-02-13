#!/bin/bash
# Quick verification script - run this on VM to check if everything is working

set -e

echo "🔍 Verifying WhatsApp bot deployment..."
echo ""

# 1. Check containers are running
echo "1️⃣ Checking containers..."
if docker compose ps whatsapp-bot api | grep -q "Up"; then
    echo "   ✅ Containers are running"
else
    echo "   ❌ Containers not running!"
    exit 1
fi

# 2. Check bot /status endpoint
echo ""
echo "2️⃣ Testing bot /status endpoint..."
STATUS_RESPONSE=$(curl -sS http://127.0.0.1:3100/status 2>/dev/null || echo "error")
if echo "$STATUS_RESPONSE" | grep -q "connected\|qr_ready\|not_ready\|disconnected"; then
    echo "   ✅ Bot /status endpoint working"
    echo "   Response: $STATUS_RESPONSE" | head -c 200
    echo ""
else
    echo "   ⚠️  Bot /status endpoint may not be ready yet"
    echo "   Response: $STATUS_RESPONSE"
fi

# 3. Check bot /health endpoint
echo ""
echo "3️⃣ Testing bot /health endpoint..."
HEALTH_RESPONSE=$(curl -sS http://127.0.0.1:3100/health 2>/dev/null || echo "error")
if echo "$HEALTH_RESPONSE" | grep -q "ok\|true"; then
    echo "   ✅ Bot /health endpoint working"
else
    echo "   ⚠️  Bot /health endpoint may not be ready yet"
fi

# 4. Check API endpoints (if token is available)
echo ""
echo "4️⃣ Testing API endpoints..."
if [ -f .env ]; then
    set -a
    source .env 2>/dev/null || true
    set +a
fi

if [ -n "${WA_QR_BRIDGE_TOKEN:-}" ]; then
    API_STATUS=$(curl -sS -H "Authorization: Bearer $WA_QR_BRIDGE_TOKEN" http://127.0.0.1:8000/admin/wa/status 2>/dev/null || echo "error")
    if echo "$API_STATUS" | grep -q "connected\|status"; then
        echo "   ✅ API /admin/wa/status endpoint working"
    else
        echo "   ⚠️  API /admin/wa/status endpoint may not be ready yet"
    fi
else
    echo "   ⚠️  WA_QR_BRIDGE_TOKEN not set, skipping API tests"
fi

# 5. Check for expected log messages
echo ""
echo "5️⃣ Checking for expected log messages..."
RECENT_LOGS=$(docker compose logs --tail 50 whatsapp-bot 2>/dev/null || echo "")

if echo "$RECENT_LOGS" | grep -q "listening on :3100"; then
    echo "   ✅ Bot is listening on port 3100"
fi

if echo "$RECENT_LOGS" | grep -q "HTTP_SERVER_STARTED\|WA_CONNECT_START"; then
    echo "   ✅ Bot initialization logs found"
fi

if echo "$RECENT_LOGS" | grep -q "QR_READY"; then
    echo "   ✅ QR code generation detected"
fi

if echo "$RECENT_LOGS" | grep -q "CONNECTED"; then
    echo "   ✅ Bot connection detected"
fi

# 6. Check file persistence
echo ""
echo "6️⃣ Checking file persistence..."
if [ -f "/opt/gni-bot-creator/data/wa-auth/last_qr.json" ]; then
    echo "   ✅ last_qr.json file exists"
    echo "   File size: $(stat -c%s /opt/gni-bot-creator/data/wa-auth/last_qr.json 2>/dev/null || echo "unknown") bytes"
else
    echo "   ℹ️  last_qr.json not created yet (will be created when QR is generated)"
fi

echo ""
echo "✅ Verification complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Trigger reconnect: curl -X POST -H \"Authorization: Bearer \$WA_QR_BRIDGE_TOKEN\" http://127.0.0.1:8000/admin/wa/reconnect"
echo "   2. Watch logs: docker compose logs -f whatsapp-bot"
echo "   3. Check QR: curl -H \"Authorization: Bearer \$WA_QR_BRIDGE_TOKEN\" http://127.0.0.1:8000/admin/wa/qr | jq ."
