#!/usr/bin/env bash
# Backup Postgres to /backups with timestamp; keep last N (BACKUP_RETENTION=7); print size and path.
#
# On VM host: run this script; it invokes the backup container.
#   /opt/gni-bot-creator/scripts/backup_postgres.sh
# In container: runs pg_dump and retention (used by docker compose backup service).
#
# Env: BACKUP_DIR (default /backups), BACKUP_RETENTION (default 7), PGHOST/PGUSER/PGPASSWORD/PGDATABASE.
set -e

BACKUP_RETENTION="${BACKUP_RETENTION:-7}"

# When not in backup container (no pg_dump or no PGHOST), run via docker and exit
if ! command -v pg_dump >/dev/null 2>&1 || [ -z "${PGHOST:-}" ]; then
  REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
  cd "$REPO_ROOT"
  export BACKUP_RETENTION
  exec docker compose --profile backup run --rm -e BACKUP_RETENTION backup
fi

# --- In container: run pg_dump and retention ---
BACKUP_DIR="${BACKUP_DIR:-/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT="${BACKUP_DIR}/gni_${TIMESTAMP}.sql"

export PGHOST="${PGHOST:-localhost}"
export PGUSER="${PGUSER:-${POSTGRES_USER:-gni}}"
export PGPASSWORD="${PGPASSWORD:-${POSTGRES_PASSWORD:-gni}}"
export PGPORT="${PGPORT:-5432}"
export PGDATABASE="${PGDATABASE:-${POSTGRES_DB:-gni}}"

mkdir -p "$BACKUP_DIR"
pg_dump -Fp "$PGDATABASE" > "$OUTPUT"

# Print path and size (portable: ls -l or du)
if [ -f "$OUTPUT" ]; then
  SIZE=$(ls -lh "$OUTPUT" 2>/dev/null | awk '{print $5}' || du -h "$OUTPUT" 2>/dev/null | cut -f1)
  echo "Backup: $OUTPUT (size: ${SIZE:-unknown})"
fi

# Retention: keep last N (portable: avoid xargs -r)
cd "$BACKUP_DIR"
ls -t gni_*.sql 2>/dev/null | tail -n +$((BACKUP_RETENTION + 1)) | while read -r f; do rm -f "$f"; done
echo "Retention: kept last $BACKUP_RETENTION backups"
