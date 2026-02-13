#!/bin/bash
# Fix VM setup: Install missing tools and verify environment
# Run this ON THE VM HOST (not inside a container)

set -e

echo "🔧 Fixing VM setup..."

# Check if we're inside a container
if [ -f /.dockerenv ] || [ -n "${DOCKER_CONTAINER:-}" ]; then
    echo "❌ ERROR: You are inside a Docker container!"
    echo "   Please exit the container first:"
    echo "   Type 'exit' to leave the container"
    echo "   Then run this script again on the VM host"
    exit 1
fi

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo "⚠️  Cannot detect OS, assuming Debian/Ubuntu"
    OS="debian"
fi

echo "Detected OS: $OS"
echo ""

# Install curl if missing
if ! command -v curl &> /dev/null; then
    echo "📦 Installing curl..."
    if [ "$OS" = "alpine" ]; then
        apk add --no-cache curl
    elif [ "$OS" = "debian" ] || [ "$OS" = "ubuntu" ]; then
        apt-get update && apt-get install -y curl
    elif [ "$OS" = "centos" ] || [ "$OS" = "rhel" ]; then
        yum install -y curl
    else
        echo "⚠️  Unknown OS, please install curl manually"
    fi
else
    echo "✓ curl is installed"
fi

# Install jq if missing
if ! command -v jq &> /dev/null; then
    echo "📦 Installing jq..."
    if [ "$OS" = "alpine" ]; then
        apk add --no-cache jq
    elif [ "$OS" = "debian" ] || [ "$OS" = "ubuntu" ]; then
        apt-get update && apt-get install -y jq
    elif [ "$OS" = "centos" ] || [ "$OS" = "rhel" ]; then
        yum install -y jq
    else
        echo "⚠️  Unknown OS, please install jq manually"
    fi
else
    echo "✓ jq is installed"
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ ERROR: Docker is not installed!"
    echo "   Please install Docker first:"
    echo "   curl -fsSL https://get.docker.com | sh"
    exit 1
else
    echo "✓ Docker is installed: $(docker --version)"
fi

# Check Docker Compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ ERROR: Docker Compose is not installed!"
    echo "   Please install Docker Compose"
    exit 1
else
    echo "✓ Docker Compose is available"
fi

# Check if project directory exists
if [ ! -d "/opt/gni-bot-creator" ]; then
    echo "⚠️  WARNING: /opt/gni-bot-creator does not exist!"
    echo "   Current directory: $(pwd)"
    echo "   Please navigate to the correct project directory"
    echo ""
    echo "   If you need to clone the repo:"
    echo "   git clone <your-repo-url> /opt/gni-bot-creator"
else
    echo "✓ Project directory exists: /opt/gni-bot-creator"
fi

echo ""
echo "✅ Setup check complete!"
echo ""
echo "📋 Next steps:"
echo "   1. cd /opt/gni-bot-creator"
echo "   2. git pull origin main"
echo "   3. docker compose up -d --build --force-recreate whatsapp-bot api"
