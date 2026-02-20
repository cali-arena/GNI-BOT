#!/usr/bin/env bash
# Strip CRLF from shell scripts. Run on VM if scripts fail with $'\r': command not found.
# Usage: bash scripts/fix_crlf.sh (run from repo root)
set -e
cd "$(dirname "$0")/.."
for f in scripts/*.sh; do
  [ -f "$f" ] && sed -i 's/\r$//' "$f" || true
done
echo "Done. CRLF stripped from scripts/*.sh"
