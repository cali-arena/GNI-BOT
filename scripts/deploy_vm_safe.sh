#!/bin/bash
# Safe deployment script for VM
# Run this ON THE VM HOST (not inside a container)

set -e  # Exit on error

echo "🚀 Deploying WhatsApp bot fixes..."

# 1. Navigate to project directory
cd /opt/gni-bot-creator || {
    echo "❌ Error: /opt/gni-bot-creator not found!"
    exit 1
}

# 2. Check git status
echo "📋 Checking git status..."
git status --short || echo "⚠️  Warning: git status check failed"

# 3. Pull latest changes
echo "📥 Pulling latest changes..."
BRANCH=$(git branch --show-current 2>/dev/null || echo "main")
echo "Current branch: $BRANCH"

if git pull origin "$BRANCH" 2>&1 | grep -q "Already up to date"; then
    echo "✓ Already up to date"
elif git pull origin main 2>&1 | grep -q "Already up to date"; then
    echo "✓ Already up to date (main branch)"
elif git pull origin master 2>&1 | grep -q "Already up to date"; then
    echo "✓ Already up to date (master branch)"
else
    echo "✓ Pulled latest changes"
fi

# 4. Rebuild and restart containers
echo ""
echo "🔨 Rebuilding WhatsApp bot and API containers..."
docker compose up -d --build --force-recreate whatsapp-bot api

# 5. Wait for containers to start
echo ""
echo "⏳ Waiting for containers to start..."
sleep 5

# 6. Check container status
echo ""
echo "📊 Container status:"
docker compose ps whatsapp-bot api

# 7. Show recent logs
echo ""
echo "📋 Recent logs (last 50 lines):"
docker compose logs --tail 50 whatsapp-bot

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 To watch logs continuously, run:"
echo "   docker compose logs -f whatsapp-bot"
echo ""
echo "🧪 To test endpoints, run:"
echo "   bash scripts/verify_wa.sh"
