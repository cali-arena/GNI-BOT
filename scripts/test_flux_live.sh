#!/usr/bin/env bash
# Live pipeline test on VM: ingest → LLM → publish to Telegram.
# Usage: bash scripts/test_flux_live.sh (on VM)
# Or: ssh gni-vm "bash /opt/gni-bot-creator/scripts/test_flux_live.sh"
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

API_URL="${API_URL:-http://localhost:8000}"

[ -f .env ] && set -a && source .env 2>/dev/null && set +a || true
CURL_AUTH=()
[ -n "${API_KEY:-}" ] && CURL_AUTH=(-H "X-API-Key: $API_KEY")

echo "=== Live Pipeline Test (Flux + Telegram) ==="
echo ""

# 1) Resume (ensure not paused)
echo "1) Resuming pipeline..."
curl -sf -X POST "${CURL_AUTH[@]}" "$API_URL/control/resume"
echo ""
echo ""

# 2) Trigger ingest (RSS + Telegram)
echo "2) Triggering ingest (RSS + Telegram)..."
curl -sf -X POST "${CURL_AUTH[@]}" "$API_URL/monitoring/run"
echo ""
echo ""

# 3) Status before
echo "3) Pipeline status (before wait)..."
curl -sf "${CURL_AUTH[@]}" "$API_URL/control/status" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))" 2>/dev/null || curl -sf "${CURL_AUTH[@]}" "$API_URL/control/status"
echo ""

# 4) Wait for worker to process (LLM, render, publish)
echo "4) Waiting 90s for worker to process (score → LLM → render → publish)..."
sleep 90

# 5) Status after
echo ""
echo "5) Pipeline status (after)..."
curl -sf "${CURL_AUTH[@]}" "$API_URL/control/status" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))" 2>/dev/null || curl -sf "${CURL_AUTH[@]}" "$API_URL/control/status"

echo ""
echo "=== Done. Check your Telegram group for new posts. ==="
