#!/usr/bin/env bash
# Wrapper to run env validation. Sources .env from repo root then runs validate_env.py.
# Usage: bash scripts/validate_env.sh [api|worker|all]
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"
[ -f .env ] && set -a && source .env 2>/dev/null && set +a || true
exec python3 scripts/validate_env.py "$@"
