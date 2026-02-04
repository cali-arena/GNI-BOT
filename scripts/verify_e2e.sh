#!/usr/bin/env bash
# E2E verification: compose up, health, ingest, publish, pause, assert blocked, summary.
# Requires: TELEGRAM_BOT_TOKEN, TELEGRAM_TARGET_CHAT_ID (or TELEGRAM_CHAT_ID), MAKE_WEBHOOK_URL
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

API_URL="${API_URL:-http://127.0.0.1:8000}"

echo "=== E2E Verification ==="

# Check required env for real publish (uses same env as worker via compose)
check_env() {
  local out ret
  set +e
  out=$(docker compose run --rm --no-deps worker python -c "
import os
m = []
if not (os.environ.get('TELEGRAM_BOT_TOKEN') or '').strip():
  m.append('TELEGRAM_BOT_TOKEN')
if not (os.environ.get('TELEGRAM_TARGET_CHAT_ID') or os.environ.get('TELEGRAM_CHAT_ID') or '').strip():
  m.append('TELEGRAM_TARGET_CHAT_ID or TELEGRAM_CHAT_ID')
if not (os.environ.get('MAKE_WEBHOOK_URL') or '').strip():
  m.append('MAKE_WEBHOOK_URL')
if m:
  print('Missing: ' + ', '.join(m))
  exit(1)
" 2>&1)
  ret=$?
  set -e
  if [ $ret -ne 0 ] || echo "$out" | grep -q "Missing:"; then
    echo "$out"
    echo "Set in .env or export. See .env.example"
    exit 1
  fi
}

check_env

# Ensure .env exists and load for API_KEY (optional auth)
[ ! -f .env ] && cp .env.example .env 2>/dev/null || true
[ -f .env ] && set -a && source .env 2>/dev/null && set +a || true

# Auth header for control endpoints when API_KEY is set
CURL_AUTH=()
[ -n "${API_KEY:-}" ] && CURL_AUTH=(-H "X-API-Key: $API_KEY")

echo "Starting services..."
docker compose up -d

echo "Waiting for health (max 180s)..."
max=180
interval=3
elapsed=0
while [ $elapsed -lt $max ]; do
  if curl -sf "$API_URL/health" >/dev/null 2>&1; then
    echo "Health OK"
    break
  fi
  sleep $interval
  elapsed=$((elapsed + interval))
done
if [ $elapsed -ge $max ]; then
  echo "Health check timed out"
  exit 1
fi

# Assert /health returns OK
health=$(curl -sf "$API_URL/health")
if ! echo "$health" | grep -q '"status".*"ok"'; then
  echo "Health check failed: $health"
  exit 1
fi
echo "curl /health: OK"

# Resume (ensure not paused)
curl -sf -X POST "${CURL_AUTH[@]}" "$API_URL/control/resume"
echo "curl POST /control/resume: OK"

# Run full pipeline: ingest RSS (5), optional Telegram (10min), score, draft, publish
echo "Running pipeline (ingest, score, draft, publish)..."
if ! docker compose run --rm -e DRY_RUN=0 worker python scripts/verify_e2e.py; then
  echo "Pipeline verification failed"
  exit 1
fi

# Pause
echo "Pausing..."
curl -sf -X POST "${CURL_AUTH[@]}" "$API_URL/control/pause"
echo "curl POST /control/pause: OK"

# Attempt publish again (must be blocked)
echo "Attempting publish while paused..."
docker compose run --rm -e DRY_RUN=0 worker python scripts/verify_e2e.py --publish-only

# Assert publish_blocked increased
status=$(curl -sf "${CURL_AUTH[@]}" "$API_URL/control/status")
blocked=$(echo "$status" | grep -o '"publish_blocked_count":[0-9]*' | cut -d: -f2)
if [ -z "$blocked" ] || [ "${blocked:-0}" -lt 1 ]; then
  echo "Expected publish_blocked_count >= 1 after pause, got: $blocked"
  exit 1
fi
echo "Publish blocked assertion: OK (publish_blocked_count=$blocked)"

# Final summary from status
echo ""
echo "=== Final Summary ==="
echo "$status" | python3 -c "
import sys, json
try:
  d = json.load(sys.stdin)
  s = d.get('stats', {})
  print('items ingested: see pipeline output above')
  print('drafts generated: see pipeline output above')
  print('publications success:', s.get('publications_sent', 0))
  print('publications failed:', s.get('failed_publications', 0))
  print('publications blocked:', s.get('publish_blocked_count', 0))
except Exception:
  print('(could not parse status)')
" 2>/dev/null || echo "$status"

echo ""
echo "ALL CHECKS PASSED"
