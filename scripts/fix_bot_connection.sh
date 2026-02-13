#!/bin/bash
# Fix WhatsApp bot connection issues
# Run this ON THE VM HOST

set -e

echo "🔧 Fixing WhatsApp bot connection..."
echo ""

# 1. Check if container exists and is running
echo "1️⃣ Checking container status..."
CONTAINER_NAME=$(docker compose ps -q whatsapp-bot 2>/dev/null || echo "")
if [ -z "$CONTAINER_NAME" ]; then
    echo "   ⚠️  Container not found - it might not be started"
    echo "   The whatsapp-bot service uses --profile whatsapp"
    echo ""
    echo "   Starting with profile..."
    docker compose --profile whatsapp up -d --build whatsapp-bot
    echo "   ✅ Container started"
else
    echo "   Container ID: $CONTAINER_NAME"
    CONTAINER_STATUS=$(docker inspect --format='{{.State.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo "unknown")
    echo "   Status: $CONTAINER_STATUS"
    
    if [ "$CONTAINER_STATUS" != "running" ]; then
        echo "   ❌ Container is not running! Restarting..."
        docker compose --profile whatsapp up -d whatsapp-bot
        sleep 5
    fi
fi

# 2. Wait for container to be ready
echo ""
echo "2️⃣ Waiting for container to be ready..."
sleep 5

# 3. Check logs for errors
echo ""
echo "3️⃣ Checking recent logs..."
docker compose logs --tail 30 whatsapp-bot | tail -15

# 4. Test connection from inside container
echo ""
echo "4️⃣ Testing connection from INSIDE container..."
docker exec "$(docker compose ps -q whatsapp-bot)" sh -c "curl -sS http://localhost:3100/health 2>&1" || {
    echo "   ❌ Connection failed inside container"
    echo "   Container might be crashing - check logs above"
    exit 1
}

# 5. Test connection from host
echo ""
echo "5️⃣ Testing connection from HOST..."
if curl -sS http://127.0.0.1:3100/health > /dev/null 2>&1; then
    echo "   ✅ Port 3100 is accessible from host!"
    curl -sS http://127.0.0.1:3100/status | jq . || echo "   (Status endpoint response shown above)"
else
    echo "   ❌ Port 3100 is NOT accessible from host"
    echo "   Checking port mapping..."
    docker port "$(docker compose ps -q whatsapp-bot)" 2>/dev/null || echo "   Port mapping issue detected"
fi

echo ""
echo "✅ Fix attempt complete!"
echo ""
echo "📋 If still not working, check:"
echo "   1. docker compose ps whatsapp-bot"
echo "   2. docker compose logs -f whatsapp-bot"
echo "   3. Ensure you're using --profile whatsapp when starting"
