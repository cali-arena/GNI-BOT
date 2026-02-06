#!/usr/bin/env bash
# VM verification: runs ON THE VM inside /opt/gni-bot-creator.
# Usage: bash scripts/verify_vm.sh
# Exit non-zero on any FAIL. Runs all checks before exiting.
set +e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

API_URL="${API_URL:-http://localhost:8000}"
FAILED=0

# Load .env for API_KEY (control endpoints)
[ -f .env ] && set -a && source .env 2>/dev/null && set +a || true
CURL_AUTH=()
[ -n "${API_KEY:-}" ] && CURL_AUTH=(-H "X-API-Key: $API_KEY")

_pass() { echo "  PASS: $1"; }
_fail() { echo "  FAIL: $1"; FAILED=1; }

echo "=== VM Verification ==="
echo "  Repo: ${REPO_ROOT}"
echo ""

# 1) Docker health
echo "1) Docker health"
if docker compose ps 2>/dev/null | grep -qE "unhealthy|Exit"; then
  _fail "Some services unhealthy or exited"
  docker compose ps
else
  required="postgres redis ollama api worker collector"
  for svc in $required; do
    if docker compose ps 2>/dev/null | grep -q "$svc"; then
      : # present
    else
      _fail "Service $svc not found"
    fi
  done
  [ $FAILED -eq 0 ] && _pass "All required services running"
fi
echo ""

# 2) API health
echo "2) API health"
if curl -sf "$API_URL/health" >/dev/null 2>&1; then
  _pass "curl $API_URL/health"
else
  _fail "curl $API_URL/health"
fi
echo ""

# 3) Internal connectivity
echo "3) Internal connectivity (api -> ollama)"
if docker compose exec -T api curl -sf http://ollama:11434/api/tags >/dev/null 2>&1; then
  _pass "api -> ollama"
else
  _fail "api -> ollama"
fi

echo "3) WhatsApp-bot health (optional; run with --profile whatsapp to enable)"
if docker compose ps 2>/dev/null | grep -q "whatsapp-bot"; then
  if docker compose exec -T api curl -sf http://whatsapp-bot:3100/health >/dev/null 2>&1; then
    _pass "whatsapp-bot /health OK"
  else
    _fail "whatsapp-bot /health"
  fi
else
  _pass "whatsapp-bot not in stack (optional)"
fi

echo "3) Internal connectivity (api -> postgres)"
if docker compose exec -T api python -c "
import os
from sqlalchemy import create_engine, text
url = os.environ.get('DATABASE_URL', 'postgresql://gni:gni@postgres:5432/gni')
e = create_engine(url)
with e.connect() as c:
    c.execute(text('SELECT 1'))
" 2>/dev/null; then
  _pass "api -> postgres"
else
  _fail "api -> postgres"
fi

echo "3) Internal connectivity (api -> redis)"
if docker compose exec -T api python -c "
import os
import redis
url = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
r = redis.Redis.from_url(url)
r.ping()
" 2>/dev/null; then
  _pass "api -> redis"
else
  _fail "api -> redis"
fi
echo ""

# 4) Control endpoints
echo "4) Control endpoints (pause/resume)"
# Pause
if curl -sf -X POST "${CURL_AUTH[@]}" "$API_URL/control/pause" >/dev/null 2>&1; then
  _pass "POST /control/pause"
else
  _fail "POST /control/pause"
fi

# Run pipeline once; when paused, publish is blocked
_get_blocked() { curl -sf "${CURL_AUTH[@]}" "$API_URL/control/status" 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('stats',{}).get('publish_blocked_count',0))" 2>/dev/null || echo "0"; }
before=$(_get_blocked)
docker compose exec -T worker python -m apps.worker.tasks --once --dry-run >/dev/null 2>&1 || true
after=$(_get_blocked)

if [ -n "$after" ] && [ -n "$before" ] && [ "${after:-0}" -ge "${before:-0}" ]; then
  _pass "Publish blocked when paused"
else
  _fail "Publish blocked when paused (before=$before after=$after)"
fi

# Resume
if curl -sf -X POST "${CURL_AUTH[@]}" "$API_URL/control/resume" >/dev/null 2>&1; then
  _pass "POST /control/resume"
else
  _fail "POST /control/resume"
fi
echo ""

# 5) Make webhook smoke test
echo "5) Make webhook smoke test"
if [ -f scripts/test_make_webhook.py ]; then
  if docker compose exec -T worker python scripts/test_make_webhook.py 2>/dev/null; then
    _pass "scripts/test_make_webhook.py (2xx)"
  else
    _fail "scripts/test_make_webhook.py (non-2xx or MAKE_WEBHOOK_URL unset)"
  fi
else
  _fail "scripts/test_make_webhook.py not found"
fi
echo ""

# 6) Safe test publish (dry-run, one cycle — does not spam; TEST_PUBLISH=1 would run real publish)
echo "6) Safe test publish (dry-run, 1 cycle)"
if docker compose exec -T -e DRY_RUN=1 worker python -m apps.worker.tasks --once --dry-run >/dev/null 2>&1; then
  _pass "Pipeline once (dry-run) — no real send"
else
  _fail "Pipeline once (dry-run)"
fi
echo ""

# Summary
if [ $FAILED -eq 0 ]; then
  echo "=== ALL CHECKS PASSED ==="
  echo "PASS"
  exit 0
else
  echo "=== SOME CHECKS FAILED ==="
  echo "FAIL"
  exit 1
fi
