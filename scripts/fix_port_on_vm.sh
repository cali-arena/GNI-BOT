#!/bin/bash
# Fix port mapping issue - run this ON THE VM
# This script will be copied to VM

set -e

echo "🔧 Fixing port 3100 mapping issue..."
echo ""

# 1. Stop and remove container completely
echo "1️⃣ Stopping and removing container..."
docker compose --profile whatsapp stop whatsapp-bot 2>/dev/null || true
docker compose --profile whatsapp rm -f whatsapp-bot 2>/dev/null || true

# 2. Verify docker-compose.yml has port mapping
echo ""
echo "2️⃣ Verifying docker-compose.yml..."
if grep -A 5 "whatsapp-bot:" docker-compose.yml | grep -q "3100:3100"; then
    echo "   ✅ Port mapping found in docker-compose.yml"
else
    echo "   ❌ Port mapping NOT found!"
    echo "   Checking docker-compose.yml..."
    grep -A 10 "whatsapp-bot:" docker-compose.yml | head -15
    exit 1
fi

# 3. Check if port 3100 is in use
echo ""
echo "3️⃣ Checking if port 3100 is in use..."
if command -v ss >/dev/null 2>&1; then
    if ss -tuln | grep -q ":3100"; then
        echo "   ⚠️  Port 3100 is already in use:"
        ss -tuln | grep ":3100"
        echo "   Killing process..."
        fuser -k 3100/tcp 2>/dev/null || true
        sleep 2
    else
        echo "   ✅ Port 3100 is free"
    fi
elif command -v netstat >/dev/null 2>&1; then
    if netstat -tuln | grep -q ":3100"; then
        echo "   ⚠️  Port 3100 is already in use"
        netstat -tuln | grep ":3100"
    else
        echo "   ✅ Port 3100 is free"
    fi
else
    echo "   ⚠️  Cannot check port (install net-tools or use ss)"
fi

# 4. Recreate container with explicit port mapping
echo ""
echo "4️⃣ Recreating container..."
docker compose --profile whatsapp up -d --force-recreate --no-deps whatsapp-bot

# 5. Wait for container to start
echo ""
echo "5️⃣ Waiting for container to start..."
sleep 5

# 6. Check container status
echo ""
echo "6️⃣ Checking container status..."
docker compose ps whatsapp-bot

# 7. Check port mapping
echo ""
echo "7️⃣ Checking port mapping..."
CONTAINER_ID=$(docker compose ps -q whatsapp-bot 2>/dev/null || echo "")
if [ -z "$CONTAINER_ID" ]; then
    echo "   ❌ Container not found!"
    exit 1
fi

PORT_MAP=$(docker inspect "$CONTAINER_ID" --format='{{range $p, $conf := .NetworkSettings.Ports}}{{$p}} -> {{(index $conf 0).HostIp}}:{{(index $conf 0).HostPort}}{{end}}' 2>/dev/null || echo "")
if [ -n "$PORT_MAP" ] && echo "$PORT_MAP" | grep -q "3100"; then
    echo "   ✅ Port mapping active: $PORT_MAP"
else
    echo "   ❌ Port mapping still not active!"
    echo "   Full port info:"
    docker inspect "$CONTAINER_ID" --format='{{json .NetworkSettings.Ports}}' | jq . 2>/dev/null || docker inspect "$CONTAINER_ID" --format='{{json .NetworkSettings.Ports}}'
    echo ""
    echo "   Trying alternative: stop all and restart..."
    docker compose --profile whatsapp down whatsapp-bot
    docker compose --profile whatsapp up -d whatsapp-bot
    sleep 5
    PORT_MAP=$(docker inspect "$(docker compose ps -q whatsapp-bot)" --format='{{range $p, $conf := .NetworkSettings.Ports}}{{$p}} -> {{(index $conf 0).HostIp}}:{{(index $conf 0).HostPort}}{{end}}' 2>/dev/null || echo "")
    if echo "$PORT_MAP" | grep -q "3100"; then
        echo "   ✅ Port mapping now active: $PORT_MAP"
    else
        echo "   ❌ Still not working. Manual fix needed."
        exit 1
    fi
fi

# 8. Test connection
echo ""
echo "8️⃣ Testing connection..."
if curl -sS http://127.0.0.1:3100/health > /dev/null 2>&1; then
    echo "   ✅ Connection successful!"
    curl -sS http://127.0.0.1:3100/health
    echo ""
    curl -sS http://127.0.0.1:3100/status | jq . 2>/dev/null || curl -sS http://127.0.0.1:3100/status
else
    echo "   ❌ Connection still failing"
    echo "   Testing from inside container..."
    docker exec "$CONTAINER_ID" sh -c "wget -qO- http://localhost:3100/health 2>&1 || echo 'FAILED'" || echo "   Cannot test from inside"
fi

echo ""
echo "✅ Fix attempt complete!"
