#!/usr/bin/env bash
# SSH into VM and cd into deploy path.
# Usage: bash scripts/ssh_vm.sh [extra args...]
set -e

VM_USER="${VM_USER:-root}"
VM_HOST="${VM_HOST:-217.216.84.81}"
VM_PATH="${VM_PATH:-/opt/gni-bot-creator}"

exec ssh -t "${VM_USER}@${VM_HOST}" "cd ${VM_PATH} && exec bash"
