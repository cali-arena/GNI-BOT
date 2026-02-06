#!/usr/bin/env bash
# Bootstrap VM: validate env, start stack, install systemd, run E2E verification.
# Run ON THE VM (e.g. inside /opt/gni-bot-creator). Finishes with PASS only if flux_e2e_verify.sh passes.
# Requires: docker, docker compose; sudo for systemd install.
# Usage: bash scripts/bootstrap_vm_all.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "=== GNI Bot — VM Bootstrap ==="
echo "  Repo: ${REPO_ROOT}"
echo ""

# 1) Preconditions
echo "1) Preconditions"

if ! command -v docker >/dev/null 2>&1; then
  echo "  FAIL: docker not installed. Install Docker first."
  exit 1
fi
echo "  PASS: docker installed"

if ! docker compose version >/dev/null 2>&1; then
  echo "  FAIL: docker compose not available. Install Docker Compose."
  exit 1
fi
echo "  PASS: docker compose available"

if [ ! -f .env ]; then
  echo "  .env missing; creating from .env.example..."
  if [ ! -f .env.example ]; then
    echo "  FAIL: .env.example not found"
    exit 1
  fi
  cp .env.example .env
  echo ""
  echo "  IMPORTANT: Edit .env with your settings (POSTGRES_PASSWORD, API_KEY, WA_QR_BRIDGE_TOKEN, etc.):"
  echo "    nano .env"
  echo ""
  echo "  Generate secrets: bash scripts/gen_secrets.sh"
  echo "  Then run bootstrap again: bash scripts/bootstrap_vm_all.sh"
  echo ""
  exit 1
fi
echo "  PASS: .env exists"
echo ""

# 2) Validate env
echo "2) Validate env"
set -a
[ -f .env ] && source .env 2>/dev/null || true
set +a
if docker compose run --rm --no-deps worker python scripts/validate_env.py all 2>/dev/null; then
  echo "  PASS: env validation"
else
  echo "  FAIL: env validation. Fix required vars (see scripts/validate_env.py)."
  exit 1
fi
echo ""

# 3) Start services
echo "3) Start services (docker compose up -d)"
docker compose up -d
echo "  Waiting for API health (max 120s)..."
for i in $(seq 1 24); do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    echo "  PASS: API ready"
    break
  fi
  sleep 5
done
if ! curl -sf http://localhost:8000/health >/dev/null 2>&1; then
  echo "  FAIL: API not ready after 120s"
  exit 1
fi
echo ""

# 4) Install systemd (24/7 after reboot)
echo "4) Install systemd"
APP_DIR="${REPO_ROOT}"
if [ "$(id -u)" -eq 0 ]; then
  APP_DIR="$APP_DIR" bash "$SCRIPT_DIR/install_systemd.sh"
else
  sudo APP_DIR="$APP_DIR" bash "$SCRIPT_DIR/install_systemd.sh"
fi
echo ""

# 5) E2E verification (must pass)
echo "5) E2E verification (flux_e2e_verify.sh)"
if bash "$SCRIPT_DIR/flux_e2e_verify.sh"; then
  echo ""
  echo "  PASS: flux_e2e_verify.sh"
else
  echo ""
  echo "  FAIL: flux_e2e_verify.sh did not pass. Fix issues and re-run bootstrap."
  exit 1
fi
echo ""

# 6) Exact commands for logs/status
echo "=== Bootstrap complete (PASS) ==="
echo ""
echo "Exact commands to check logs and status:"
echo ""
echo "  # Service status"
echo "  sudo systemctl status gni-bot"
echo ""
echo "  # Compose and app logs"
echo "  cd ${REPO_ROOT} && docker compose logs -f"
echo ""
echo "  # API health"
echo "  curl http://localhost:8000/health"
echo ""
echo "  # Pause publishing"
echo "  curl -X POST http://localhost:8000/control/pause"
echo "  # (add -H \"X-API-Key: \$API_KEY\" if API_KEY is set)"
echo ""
echo "  # Resume publishing"
echo "  curl -X POST http://localhost:8000/control/resume"
echo ""
echo "  # After reboot, stack comes back automatically; verify with:"
echo "  curl http://localhost:8000/health"
echo "  sudo systemctl status gni-bot"
echo ""
