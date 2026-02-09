#!/bin/bash
# Verify port mapping is fixed - run this ON THE VM

set -e

echo "🔍 Verifying port mapping fix..."
echo ""

# 1. Check container is running
echo "1️⃣ Checking container status..."
if docker compose ps whatsapp-bot | grep -q "Up"; then
    echo "   ✅ Container is running"
else
    echo "   ❌ Container is not running!"
    exit 1
fi

# 2. Check port mapping
echo ""
echo "2️⃣ Checking port mapping..."
CONTAINER_ID=$(docker compose ps -q whatsapp-bot 2>/dev/null || echo "")
if [ -z "$CONTAINER_ID" ]; then
    echo "   ❌ Container not found!"
    exit 1
fi

PORT_MAP=$(docker inspect "$CONTAINER_ID" --format='{{json .NetworkSettings.Ports}}' | jq -r '.["3100/tcp"][0].HostPort // "null"' 2>/dev/null || echo "null")

if [ "$PORT_MAP" != "null" ] && [ -n "$PORT_MAP" ]; then
    echo "   ✅ Port mapping active: 3100/tcp -> 0.0.0.0:$PORT_MAP"
else
    echo "   ❌ Port mapping still null!"
    echo "   Full port info:"
    docker inspect "$CONTAINER_ID" --format='{{json .NetworkSettings.Ports}}' | jq .
    echo ""
    echo "   ⚠️  You need to manually edit docker-compose.yml:"
    echo "   Change: - \"3100:3100\""
    echo "   To:     - \"0.0.0.0:3100:3100\""
    exit 1
fi

# 3. Check if port is listening on host
echo ""
echo "3️⃣ Checking if port 3100 is listening on host..."
if ss -tuln 2>/dev/null | grep -q ":3100"; then
    echo "   ✅ Port 3100 is listening:"
    ss -tuln | grep ":3100"
elif netstat -tuln 2>/dev/null | grep -q ":3100"; then
    echo "   ✅ Port 3100 is listening:"
    netstat -tuln | grep ":3100"
else
    echo "   ⚠️  Port 3100 not found in listening ports"
fi

# 4. Test connection
echo ""
echo "4️⃣ Testing connection..."
if curl -sS http://127.0.0.1:3100/health > /dev/null 2>&1; then
    echo "   ✅ Connection successful!"
    echo ""
    echo "   Health endpoint:"
    curl -sS http://127.0.0.1:3100/health
    echo ""
    echo ""
    echo "   Status endpoint:"
    curl -sS http://127.0.0.1:3100/status | jq . 2>/dev/null || curl -sS http://127.0.0.1:3100/status
else
    echo "   ❌ Connection failed!"
    echo "   Testing from inside container..."
    docker exec "$CONTAINER_ID" sh -c "wget -qO- http://localhost:3100/health 2>&1" || echo "   ⚠️  Cannot test from inside container"
fi

echo ""
echo "✅ Verification complete!"
