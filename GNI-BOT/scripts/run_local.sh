#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

echo "Starting services..."
docker compose up -d

echo "Waiting for healthchecks (max 120s)..."
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
