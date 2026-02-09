#!/bin/bash
# Deployment script for WhatsApp bot fixes
# Run this ON THE VM (SSH into 217.216.84.81 first)

set -e  # Exit on error

echo "🚀 Deploying WhatsApp bot fixes to VM..."

# 1. Navigate to project directory
cd /opt/gni-bot-creator || {
    echo "❌ Error: /opt/gni-bot-creator not found!"
    exit 1
}

# 2. Pull latest changes from git
echo "📥 Pulling latest changes..."
git pull origin main || git pull origin master || {
    echo "⚠️  Warning: git pull failed, continuing with existing code..."
}

# 3. Rebuild and restart WhatsApp bot + API
echo "🔨 Rebuilding WhatsApp bot and API containers..."
docker compose up -d --build --force-recreate whatsapp-bot api

# 4. Wait for containers to start
echo "⏳ Waiting for containers to start..."
sleep 5

# 5. Check container status
echo "📊 Container status:"
docker compose ps whatsapp-bot api

# 6. Test endpoints
echo ""
echo "🧪 Testing endpoints..."
echo ""

# Load environment variables
if [ -f .env ]; then
    set -a
    source .env
    set +a
else
    echo "⚠️  Warning: .env file not found"
fi

# Test bot /status endpoint
echo "1. Testing bot /status endpoint:"
curl -sS http://127.0.0.1:3100/status 2>/dev/null | jq . || echo "   ⚠️  Bot /status not ready yet"

# Test bot /debug/auth endpoint
echo ""
echo "2. Testing bot /debug/auth endpoint:"
curl -sS http://127.0.0.1:3100/debug/auth 2>/dev/null | jq . || echo "   ⚠️  Bot /debug/auth not ready yet"

# Test API /admin/wa/status endpoint
if [ -n "$WA_QR_BRIDGE_TOKEN" ]; then
    echo ""
    echo "3. Testing API /admin/wa/status endpoint:"
    curl -sS -H "Authorization: Bearer $WA_QR_BRIDGE_TOKEN" http://127.0.0.1:8000/admin/wa/status 2>/dev/null | jq . || echo "   ⚠️  API /admin/wa/status not ready yet"
else
    echo ""
    echo "⚠️  Warning: WA_QR_BRIDGE_TOKEN not set, skipping API tests"
fi

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Watch logs: docker compose logs -f whatsapp-bot"
echo "   2. Trigger reconnect: curl -X POST -H \"Authorization: Bearer \$WA_QR_BRIDGE_TOKEN\" http://127.0.0.1:8000/admin/wa/reconnect"
echo "   3. Check QR: curl -H \"Authorization: Bearer \$WA_QR_BRIDGE_TOKEN\" http://127.0.0.1:8000/admin/wa/qr | jq ."
