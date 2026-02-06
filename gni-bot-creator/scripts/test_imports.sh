#!/usr/bin/env bash
# Quick import self-test for api and worker containers. Exit 0 only if all imports succeed.
# Usage: ./scripts/test_imports.sh [api|worker|all]
# Requires: docker compose up -d (api and/or worker running)
set -e
cd "$(dirname "$0")/.."

run_api() {
  docker compose exec -T api python -c "
import apps
import apps.api
import apps.api.core.settings
print('OK')
"
}

run_worker() {
  docker compose exec -T worker python -c "
import apps
import apps.api
import apps.worker.tasks
print('OK')
"
}

case "${1:-all}" in
  api)   run_api ;;
  worker) run_worker ;;
  all)
    echo -n "api: "   && run_api
    echo -n "worker: " && run_worker
    ;;
  *) echo "Usage: $0 [api|worker|all]" >&2; exit 1 ;;
esac
