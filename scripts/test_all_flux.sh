#!/usr/bin/env bash
# Full flux test on VM: health → resume → ingest → worker (score → LLM draft → publish).
# Usage:
#   bash scripts/test_all_flux.sh          # dry-run (no real Telegram/websites)
#   bash scripts/test_all_flux.sh --real   # real publish to Telegram + Make webhook
# Or via SSH: ssh gni-vm "cd /opt/gni-bot-creator && bash scripts/test_all_flux.sh [--real]"
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

API_URL="${API_URL:-http://localhost:8000}"
REAL_PUBLISH=false
[[ "${1:-}" == "--real" ]] && REAL_PUBLISH=true

[ -f .env ] && set -a && source .env 2>/dev/null && set +a || true
CURL_AUTH=()
[ -n "${API_KEY:-}" ] && CURL_AUTH=(-H "X-API-Key: $API_KEY")

echo "=== Full Flux Test (Ingest → LLM → Telegram + Websites) ==="
echo "  Mode: $([ "$REAL_PUBLISH" = true ] && echo 'REAL PUBLISH' || echo 'DRY-RUN (no send)')"
echo ""

# 1) Health
echo "1) Health check..."
if ! curl -sf "$API_URL/health" >/dev/null 2>&1; then
  echo "   FAIL: API not reachable at $API_URL/health"
  exit 1
fi
echo "   OK"
echo ""

# 2) Worker -> Ollama connectivity
echo "2) Worker -> Ollama..."
if ! docker compose exec -T worker python -c "import httpx; r=httpx.get('http://ollama:11434/api/version',timeout=5); exit(0 if r.status_code==200 else 1)" 2>/dev/null; then
  echo "   WARN: worker may not reach Ollama (LLM draft can fail)"
else
  echo "   OK"
fi
echo ""

# 3) Resume (ensure not paused)
echo "3) Resuming pipeline..."
curl -sf -X POST "${CURL_AUTH[@]}" "$API_URL/control/resume" >/dev/null 2>&1 || true
echo "   OK"
echo ""

# 4) Trigger ingest (RSS + Telegram)
echo "4) Triggering ingest..."
curl -sf -X POST "${CURL_AUTH[@]}" "$API_URL/monitoring/run" >/dev/null 2>&1 || true
echo "   OK"
echo ""

# 5) Status before
echo "5) Status before worker run..."
curl -sf "${CURL_AUTH[@]}" "$API_URL/control/status" 2>/dev/null | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))" 2>/dev/null || curl -sf "${CURL_AUTH[@]}" "$API_URL/control/status"
echo ""

# 6) Run worker once (score → LLM draft → publish)
echo "6) Running worker once (score → LLM draft → publish)..."
if [ "$REAL_PUBLISH" = true ]; then
  docker compose exec -T -e DRY_RUN=0 worker python -m apps.worker.tasks --once --no-dry-run
else
  docker compose exec -T -e DRY_RUN=1 worker python -m apps.worker.tasks --once --dry-run
fi
echo ""

# 7) Status after
echo "7) Status after worker run..."
curl -sf "${CURL_AUTH[@]}" "$API_URL/control/status" 2>/dev/null | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))" 2>/dev/null || curl -sf "${CURL_AUTH[@]}" "$API_URL/control/status"
echo ""

echo "=== Done ==="
if [ "$REAL_PUBLISH" = true ]; then
  echo "Check your Telegram group and websites for new posts."
else
  echo "This was a DRY-RUN. No posts were sent. For real publish: bash scripts/test_all_flux.sh --real"
fi
