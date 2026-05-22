#!/bin/bash
set -euo pipefail

# Configuration
DB_NAME="${POSTGRES_DB:-tfe_cycling}"
DB_USER="${POSTGRES_USER:-tfe_user}"
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"
BACKUP_DIR="/var/backups/postgres"
RETENTION_DAYS=30
RETENTION_WEEKS=12
LOG_FILE="/var/log/pg_backup.log"

log() { echo "[$(date '+%Y-%m-%dT%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
die() { log "ERROR: $*"; exit 1; }

mkdir -p "$BACKUP_DIR"/{daily,weekly}

TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
DAY_OF_WEEK=$(date '+%u')

DUMP_FILE="$BACKUP_DIR/daily/${DB_NAME}_${TIMESTAMP}.dump"

log "Starting backup -> $DUMP_FILE"
PGPASSWORD="${PGPASSWORD}" pg_dump \
  -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" \
  -Fc --no-acl --no-owner \
  "$DB_NAME" > "$DUMP_FILE" || die "pg_dump failed"

pg_restore --list "$DUMP_FILE" > /dev/null || die "dump corrupted"

DUMP_SIZE=$(du -sh "$DUMP_FILE" | cut -f1)
log "Backup OK — size: $DUMP_SIZE"

if [ "$DAY_OF_WEEK" -eq 7 ]; then
  WEEKLY_FILE="$BACKUP_DIR/weekly/${DB_NAME}_week$(date '+%Y%W').dump"
  cp "$DUMP_FILE" "$WEEKLY_FILE"
  log "Weekly copy -> $WEEKLY_FILE"
fi

find "$BACKUP_DIR/daily"  -name "*.dump" -mtime +"$RETENTION_DAYS"  -delete
find "$BACKUP_DIR/weekly" -name "*.dump" -mtime +"$((RETENTION_WEEKS * 7))" -delete
log "Purge completed (daily > ${RETENTION_DAYS}d, weekly > ${RETENTION_WEEKS}w)"

log "=== Backup finished ==="