#!/usr/bin/env bash
# Verify worker imports cleanly with empty env vars (e.g. CACHE_TTL_SECONDS="").
# Exit 0 only if import succeeds; non-zero on failure.
# Usage: ./scripts/verify_worker_startup.sh  (from repo root or scripts dir)
# CI: run from project root (gni-bot-creator).
set -e
cd "$(dirname "$0")/.."
export CACHE_TTL_SECONDS=""
export PYTHONPATH="${PWD}${PYTHONPATH:+:$PYTHONPATH}"
python -c "import apps.worker.cache; print('OK')"
