#!/bin/bash
# Diagnose WhatsApp bot connection issues
# Run this ON THE VM HOST

set -e

echo "🔍 Diagnosing WhatsApp bot connection issues..."
echo ""

# 1. Check if container is running
echo "1️⃣ Checking container status..."
CONTAINER_STATUS=$(docker compose ps whatsapp-bot --format json 2>/dev/null | jq -r '.[0].State' || echo "unknown")
echo "   Container state: $CONTAINER_STATUS"

if [ "$CONTAINER_STATUS" != "running" ]; then
    echo "   ❌ Container is not running!"
    echo "   Checking logs..."
    docker compose logs --tail 50 whatsapp-bot
    exit 1
fi

# 2. Check if port is listening INSIDE container
echo ""
echo "2️⃣ Checking if port 3100 is listening INSIDE container..."
docker exec gni-bot-creator-whatsapp-bot-1 sh -c "netstat -tuln | grep 3100 || ss -tuln | grep 3100 || echo 'Port check failed'" 2>/dev/null || echo "   ⚠️  Cannot check port inside container"

# 3. Check if port is exposed on host
echo ""
echo "3️⃣ Checking if port 3100 is exposed on HOST..."
if netstat -tuln 2>/dev/null | grep -q ":3100" || ss -tuln 2>/dev/null | grep -q ":3100"; then
    echo "   ✅ Port 3100 is listening on host"
else
    echo "   ❌ Port 3100 is NOT listening on host!"
    echo "   This means the port mapping might be broken"
fi

# 4. Check container logs for errors
echo ""
echo "4️⃣ Checking recent logs for errors..."
docker compose logs --tail 100 whatsapp-bot | tail -20

# 5. Try to connect from inside container
echo ""
echo "5️⃣ Testing connection from INSIDE container..."
docker exec gni-bot-creator-whatsapp-bot-1 sh -c "curl -sS http://localhost:3100/health 2>&1 || echo 'Connection failed inside container'" || echo "   ⚠️  Cannot test from inside container"

# 6. Check docker-compose port mapping
echo ""
echo "6️⃣ Checking docker-compose port mapping..."
docker compose config | grep -A 5 "whatsapp-bot:" | grep -E "ports:|3100" || echo "   ⚠️  Cannot find port mapping"

# 7. Check if API can reach bot
echo ""
echo "7️⃣ Testing API -> Bot connection..."
if [ -f .env ]; then
    set -a
    source .env 2>/dev/null || true
    set +a
fi

if [ -n "${WA_QR_BRIDGE_TOKEN:-}" ]; then
    API_RESPONSE=$(curl -sS -H "Authorization: Bearer $WA_QR_BRIDGE_TOKEN" http://127.0.0.1:8000/admin/wa/status 2>/dev/null || echo "error")
    echo "   API response: $API_RESPONSE"
else
    echo "   ⚠️  WA_QR_BRIDGE_TOKEN not set"
fi

echo ""
echo "✅ Diagnosis complete!"
echo ""
echo "📋 Common fixes:"
echo "   1. Restart container: docker compose restart whatsapp-bot"
echo "   2. Check docker-compose.yml port mapping: ports: ['3100:3100']"
echo "   3. Check if bot is crashing: docker compose logs -f whatsapp-bot"
