#!/usr/bin/env bash
# Tail docker compose logs on VM.
# Usage: bash scripts/tail_vm_logs.sh [extra args...]
set -e

VM_USER="${VM_USER:-root}"
VM_HOST="${VM_HOST:-217.216.84.81}"
VM_PATH="${VM_PATH:-/opt/gni-bot-creator}"

# Pass extra args (e.g. api, worker) into remote command
REMOTE_CMD="cd ${VM_PATH} && docker compose logs -f --tail=200"
if [ "$#" -gt 0 ]; then
  REMOTE_CMD="${REMOTE_CMD} $(printf '%q ' "$@")"
fi
exec ssh "${VM_USER}@${VM_HOST}" "$REMOTE_CMD"
