#!/usr/bin/env bash
# VM troubleshooting: check services, WhatsApp bot, worker DRY_RUN, DB counts.
# Run from repo root: bash scripts/troubleshoot_vm.sh
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== GNI VM troubleshoot (repo: $REPO_ROOT) ==="

# 1. Running services
echo ""
echo "--- Services (docker compose ps) ---"
docker compose ps 2>/dev/null || true

# 2. WhatsApp bot (optional profile)
echo ""
if docker compose logs whatsapp-bot --tail 1 2>/dev/null | grep -q .; then
  echo "--- WhatsApp bot: RUNNING ---"
  docker compose logs whatsapp-bot --tail 10 2>/dev/null || true
else
  echo "--- WhatsApp bot: NOT RUNNING ---"
  echo "To enable QR/WhatsApp, run: docker compose --profile whatsapp up -d"
fi

# 3. Worker DRY_RUN
echo ""
echo "--- Worker DRY_RUN ---"
if [ -f .env ]; then
  dr=$(grep -E '^DRY_RUN=' .env 2>/dev/null || true)
  if [ -n "$dr" ]; then
    echo ".env: $dr"
    if echo "$dr" | grep -qE '^DRY_RUN=(1|true|yes)'; then
      echo "  -> Worker is in dry-run (no real publish). Set DRY_RUN=0 for production."
    fi
  else
    echo ".env has no DRY_RUN (compose default is 1)"
    echo "  -> Set DRY_RUN=0 in .env for production publish."
  fi
else
  echo "No .env found"
fi

# 4. DB counts (optional; postgres must be up)
echo ""
echo "--- DB counts (items by status) ---"
if docker compose exec -T postgres psql -U gni -d gni -t -c "SELECT status, COUNT(*) FROM items GROUP BY status ORDER BY status;" 2>/dev/null; then
  echo ""
  echo "--- Publications count ---"
  docker compose exec -T postgres psql -U gni -d gni -t -c "SELECT COUNT(*) FROM publications;" 2>/dev/null || true
else
  echo "Could not query DB (is postgres up?)"
fi

echo ""
echo "=== Done. See docs/RUNBOOK.md for fixes. ==="
