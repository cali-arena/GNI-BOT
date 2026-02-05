#!/usr/bin/env bash
# Validate env vars for api|worker|all. Loads .env from repo root. Exit 1 if invalid/missing.
# Usage: ./scripts/validate_env.sh [api|worker|all]
# From container: docker compose exec api python -c "from apps.shared.env_validation import validate_env; validate_env('api')"
set -e
cd "$(dirname "$0")/.."
python scripts/validate_env.py "$@"
