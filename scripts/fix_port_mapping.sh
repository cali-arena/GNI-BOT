#!/bin/bash
# Fix port mapping issue for whatsapp-bot
# Run this ON THE VM HOST

set -e

echo "🔧 Fixing port mapping for whatsapp-bot..."
echo ""

# 1. Check current port mapping
echo "1️⃣ Checking current port mapping..."
docker port $(docker compose ps -q whatsapp-bot 2>/dev/null) 2>/dev/null || echo "   ⚠️  Cannot get port mapping"

# 2. Check if port 3100 is in use
echo ""
echo "2️⃣ Checking if port 3100 is in use..."
if netstat -tuln 2>/dev/null | grep -q ":3100" || ss -tuln 2>/dev/null | grep -q ":3100"; then
    echo "   Port 3100 is in use:"
    netstat -tuln 2>/dev/null | grep ":3100" || ss -tuln 2>/dev/null | grep ":3100"
else
    echo "   Port 3100 is NOT in use on host"
fi

# 3. Stop and remove container
echo ""
echo "3️⃣ Stopping and removing container..."
docker compose --profile whatsapp stop whatsapp-bot
docker compose --profile whatsapp rm -f whatsapp-bot

# 4. Verify docker-compose.yml has correct port mapping
echo ""
echo "4️⃣ Verifying docker-compose.yml port mapping..."
if grep -A 5 "whatsapp-bot:" docker-compose.yml | grep -q '3100:3100'; then
    echo "   ✅ Port mapping found in docker-compose.yml"
else
    echo "   ❌ Port mapping NOT found in docker-compose.yml!"
    echo "   Please check docker-compose.yml has:"
    echo "     ports:"
    echo "       - \"3100:3100\""
    exit 1
fi

# 5. Recreate container
echo ""
echo "5️⃣ Recreating container with port mapping..."
docker compose --profile whatsapp up -d --force-recreate whatsapp-bot

# 6. Wait for container to start
echo ""
echo "6️⃣ Waiting for container to start..."
sleep 5

# 7. Check port mapping again
echo ""
echo "7️⃣ Verifying port mapping..."
PORT_MAPPING=$(docker port $(docker compose ps -q whatsapp-bot) 2>/dev/null || echo "")
if echo "$PORT_MAPPING" | grep -q "3100"; then
    echo "   ✅ Port mapping active:"
    echo "   $PORT_MAPPING"
else
    echo "   ❌ Port mapping still not active!"
    echo "   Checking container status..."
    docker compose ps whatsapp-bot
    exit 1
fi

# 8. Test connection
echo ""
echo "8️⃣ Testing connection..."
if curl -sS http://127.0.0.1:3100/health > /dev/null 2>&1; then
    echo "   ✅ Connection successful!"
    echo ""
    echo "   Testing endpoints:"
    curl -sS http://127.0.0.1:3100/health
    echo ""
    curl -sS http://127.0.0.1:3100/status
    echo ""
else
    echo "   ❌ Connection still failing"
    echo "   Checking container logs..."
    docker compose logs --tail 20 whatsapp-bot
    exit 1
fi

echo ""
echo "✅ Port mapping fixed!"
