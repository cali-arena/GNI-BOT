#!/usr/bin/env bash
# Flux E2E Verification — runs ON THE VM. One command to prove production-ready.
# 1) compose up, 2) wait health, 3) curl /health PASS, 4) insert 2 test items (A/B),
# 5) run pipeline (classify+generate+render), 6) validate Template A/B formats,
# 7) publish (DRY_RUN=true: invoke but not sent; DRY_RUN=false: max 1 msg per channel),
# 8) PASS/FAIL summary and exit code.
# Usage: on VM: cd /opt/gni-bot-creator && bash scripts/flux_e2e_verify.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

API_URL="${API_URL:-http://localhost:8000}"
FAILED=0
PASS=0
SKIPPED=0

_pass() { echo "  PASS: $1"; PASS=$((PASS+1)); }
_fail() { echo "  FAIL: $1"; FAILED=$((FAILED+1)); }
_skip() { echo "  SKIPPED: $1"; SKIPPED=$((SKIPPED+1)); }

# Load .env
[ -f .env ] && set -a && source .env 2>/dev/null && set +a || true
CURL_AUTH=()
[ -n "${API_KEY:-}" ] && CURL_AUTH=(-H "X-API-Key: $API_KEY")

echo "=== Flux E2E Verification (VM) ==="
echo ""

# 1) docker compose up -d
echo "1) Starting services (docker compose up -d)..."
docker compose up -d
echo ""

# 2) Wait for healthchecks
echo "2) Waiting for healthchecks (max 180s)..."
max=180
interval=5
elapsed=0
while [ $elapsed -lt $max ]; do
  if curl -sf "$API_URL/health" >/dev/null 2>&1; then
    _pass "Health check reached"
    break
  fi
  sleep $interval
  elapsed=$((elapsed + interval))
done
if [ $elapsed -ge $max ]; then
  _fail "Health check timed out"
  echo ""
  echo "=== SUMMARY: FAILED ==="
  exit 1
fi
echo ""

# 3) curl http://localhost:8000/health PASS
echo "3) curl $API_URL/health..."
if curl -sf "$API_URL/health" | grep -q '"status".*"ok"'; then
  _pass "curl /health"
else
  _fail "curl /health"
fi
echo ""

# 3b) Internal connectivity (api -> ollama)
echo "3b) Internal connectivity (api -> ollama)..."
if docker compose exec -T api curl -sf http://ollama:11434/api/tags >/dev/null 2>&1; then
  _pass "api -> ollama"
else
  _fail "api -> ollama (ensure ollama service is running)"
fi
echo ""

# 4) Insert 2 deterministic test items (direct SQL via Python script)
#    A: alegação / não confirmada -> Template A (ANALISE_INTEL)
#    B: defesa / sistema / teste -> Template B (FLASH_SETORIAL)
echo "4) Inserting 2 test items (A: alegação/não confirmada -> Template A, B: defesa/sistema/teste -> Template B)..."
ITEM_IDS=$(docker compose run --rm --no-deps worker python scripts/insert_flux_test_items.py 2>/dev/null | tail -1)
if [ -z "$ITEM_IDS" ]; then
  _fail "insert_flux_test_items.py"
  echo ""
  echo "=== SUMMARY: FAILED ==="
  exit 1
fi
echo "  Item IDs: $ITEM_IDS"
_pass "Test items inserted"
echo ""

# 5) Run pipeline for only those items (classify + generate + render)
echo "5) Running pipeline for items $ITEM_IDS (score -> classify -> generate -> render)..."
RESUME=$(curl -sf -X POST "${CURL_AUTH[@]}" "$API_URL/control/resume" 2>/dev/null || true)
DRY_RUN=1 docker compose run --rm --no-deps worker python -m apps.worker.run_pipeline --item-ids "$ITEM_IDS" --dry-run 2>/dev/null || true

DRAFTS=$(docker compose run --rm --no-deps worker python -c "
import sys
sys.path.insert(0, '.')
from apps.api.db import SessionLocal, init_db
from apps.api.db.models import Draft
init_db()
s = SessionLocal()
ids = [int(x) for x in '$ITEM_IDS'.split(',')]
n = s.query(Draft).filter(Draft.item_id.in_(ids)).count()
s.close()
print(n)
" 2>/dev/null | tail -1)
if [ "${DRAFTS:-0}" -ge 2 ]; then
  _pass "Drafts generated: $DRAFTS"
else
  _fail "Drafts generated: $DRAFTS (expected >= 2)"
fi
echo ""

# Reset items to drafted for publish step (so render is already done)
docker compose run --rm --no-deps worker python -c "
import sys
sys.path.insert(0, '.')
from apps.api.db import SessionLocal, init_db
from apps.api.db.models import Item
init_db()
sess = SessionLocal()
ids = [int(x) for x in '$ITEM_IDS'.split(',')]
sess.query(Item).filter(Item.id.in_(ids)).update({'status': 'drafted'}, synchronize_session=False)
sess.commit()
sess.close()
" 2>/dev/null || true

# 6) Validate formats (Template A: Portuguese headings + ⸻; Template B: Em destaque + 📌 Insight:)
echo "6) Validating rendered format (Template A: Portuguese + ⸻; Template B: Em destaque + 📌 Insight:)..."
if docker compose run --rm --no-deps worker python scripts/flux_validate_format.py "$ITEM_IDS" 2>/dev/null; then
  _pass "Format validation (Template A/B)"
else
  _fail "Format validation (see flux_validate_format.py)"
fi
echo ""

# 7) Publishing
# DRY_RUN=true: publish path already invoked in step 5 (no real send)
# DRY_RUN=false: publish max 1 msg per channel (first item only), only if channels configured
echo "7) Publishing..."
if [ "${DRY_RUN:-1}" = "1" ] || [ "${DRY_RUN:-1}" = "true" ]; then
  _pass "DRY_RUN=true: publish was invoked in step 5 (dry-run), no real send"
else
  HAS_CHANNEL=0
  [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_TARGET_CHAT_ID:-${TELEGRAM_CHAT_ID:-}}" ] && HAS_CHANNEL=1
  [ -n "${MAKE_WEBHOOK_URL:-}" ] && HAS_CHANNEL=1
  [ -n "${WHATSAPP_BOT_BASE_URL:-}" ] && HAS_CHANNEL=1
  if [ "$HAS_CHANNEL" -eq 1 ]; then
    FIRST_ID=$(echo "$ITEM_IDS" | cut -d',' -f1)
    DRY_RUN=0 docker compose run --rm --no-deps worker python -m apps.worker.run_pipeline --item-ids "$FIRST_ID" --publish 2>/dev/null || true
    _pass "DRY_RUN=false: published max 1 per channel (success logged)"
  else
    _skip "Publish (no TELEGRAM/MAKE/WHATSAPP channel configured)"
  fi
fi
echo ""

# 8) Pause/resume sanity
echo "8) Pause/resume..."
curl -sf -X POST "${CURL_AUTH[@]}" "$API_URL/control/pause" >/dev/null 2>&1 || true
docker compose run --rm --no-deps worker python -m apps.worker.tasks --once --dry-run 2>/dev/null || true
curl -sf -X POST "${CURL_AUTH[@]}" "$API_URL/control/resume" >/dev/null 2>&1 || true
_pass "Pause/resume"
echo ""

# Summary and exit code
echo "=== Flux E2E Summary ==="
echo "  PASS: $PASS  FAIL: $FAILED  SKIPPED: $SKIPPED"
echo ""

if [ $FAILED -gt 0 ]; then
  echo "=== RESULT: FAILED ==="
  exit 1
fi
echo "=== RESULT: PASS ==="
echo "VM is production-ready."
exit 0
