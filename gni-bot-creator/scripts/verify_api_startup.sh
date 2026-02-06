#!/usr/bin/env bash
# Verify API image build, stack startup, and /health. Exit 0 only if health returns OK.
# Usage: from repo root, ./scripts/verify_api_startup.sh
set -e
cd "$(dirname "$0")/.."

echo "Building API image..."
docker compose build api

echo "Starting stack..."
docker compose up -d

echo "Waiting for /health (max 120s)..."
max=120
interval=3
elapsed=0
while [ $elapsed -lt $max ]; do
  if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "OK"
    exit 0
  fi
  sleep $interval
  elapsed=$((elapsed + interval))
done

echo "FAIL"
exit 1
