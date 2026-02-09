#!/bin/bash
# Debug port mapping issue - comprehensive check
# Run this ON THE VM HOST

set -e

echo "🔍 Comprehensive port mapping debug..."
echo ""

# 1. Check docker-compose config
echo "1️⃣ Checking docker-compose configuration..."
docker compose config --services | grep whatsapp || echo "   ⚠️  whatsapp-bot not in config"

echo ""
echo "2️⃣ Checking whatsapp-bot service config..."
docker compose config | grep -A 20 "whatsapp-bot:" | head -25

# 3. Check actual container port mapping
echo ""
echo "3️⃣ Checking actual container port mapping..."
CONTAINER_ID=$(docker compose ps -q whatsapp-bot 2>/dev/null || echo "")
if [ -z "$CONTAINER_ID" ]; then
    echo "   ❌ Container not found!"
    exit 1
fi

echo "   Container ID: $CONTAINER_ID"
docker inspect "$CONTAINER_ID" --format='{{range $p, $conf := .NetworkSettings.Ports}}{{$p}} -> {{(index $conf 0).HostIp}}:{{(index $conf 0).HostPort}}{{end}}' 2>/dev/null || echo "   ⚠️  No port mapping found"

# 4. Check network configuration
echo ""
echo "4️⃣ Checking network configuration..."
docker inspect "$CONTAINER_ID" --format='{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{end}}' 2>/dev/null

# 5. Try connecting from inside container
echo ""
echo "5️⃣ Testing from INSIDE container..."
docker exec "$CONTAINER_ID" sh -c "curl -sS http://localhost:3100/health 2>&1 || echo 'FAILED'" || echo "   ⚠️  Cannot exec into container"

# 6. Check if port is listening on host
echo ""
echo "6️⃣ Checking if port 3100 is listening on HOST..."
if netstat -tuln 2>/dev/null | grep -q ":3100"; then
    echo "   ✅ Port 3100 is listening:"
    netstat -tuln | grep ":3100"
elif ss -tuln 2>/dev/null | grep -q ":3100"; then
    echo "   ✅ Port 3100 is listening:"
    ss -tuln | grep ":3100"
else
    echo "   ❌ Port 3100 is NOT listening on host"
fi

# 7. Check docker-compose.yml syntax
echo ""
echo "7️⃣ Checking docker-compose.yml syntax..."
if docker compose config > /dev/null 2>&1; then
    echo "   ✅ docker-compose.yml syntax is valid"
else
    echo "   ❌ docker-compose.yml has syntax errors!"
    docker compose config 2>&1 | head -10
fi

# 8. Show full container inspect
echo ""
echo "8️⃣ Full container port info:"
docker inspect "$CONTAINER_ID" --format='{{json .NetworkSettings.Ports}}' | jq . 2>/dev/null || docker inspect "$CONTAINER_ID" --format='{{json .NetworkSettings.Ports}}'

echo ""
echo "✅ Debug complete!"
