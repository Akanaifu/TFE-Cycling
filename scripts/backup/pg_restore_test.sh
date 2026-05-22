#!/bin/bash
set -euo pipefail

BACKUP_DIR="/var/backups/postgres"
TEST_DB="${POSTGRES_DB:-tfe_cycling}_restore_test"
DB_USER="${POSTGRES_USER:-tfe_user}"
DB_HOST="${POSTGRES_HOST:-localhost}"
REPORT_FILE="/var/log/pg_restore_test_$(date '+%Y%m%d').log"

log() { echo "[$(date '+%Y-%m-%dT%H:%M:%S')] $*" | tee -a "$REPORT_FILE"; }
die() { log "FAIL: $*"; cleanup; exit 1; }

cleanup() {
  PGPASSWORD="${PGPASSWORD}" psql \
    -h "$DB_HOST" -U "$DB_USER" -c "DROP DATABASE IF EXISTS \"$TEST_DB\";" \
    postgres 2>/dev/null || true
}
trap cleanup EXIT

DUMP=$(find "$BACKUP_DIR/daily" -name "*.dump" | sort | tail -1)
[ -z "$DUMP" ] && die "No dump found in $BACKUP_DIR/daily"
log "Selected dump: $DUMP"

PGPASSWORD="${PGPASSWORD}" psql \
  -h "$DB_HOST" -U "$DB_USER" \
  -c "CREATE DATABASE \"$TEST_DB\";" postgres || die "Cannot create test DB"

PGPASSWORD="${PGPASSWORD}" pg_restore \
  -h "$DB_HOST" -U "$DB_USER" \
  -d "$TEST_DB" --no-acl --no-owner "$DUMP" || die "pg_restore failed"

log "Restore OK"

TABLE_COUNT=$(PGPASSWORD="${PGPASSWORD}" psql \
  -h "$DB_HOST" -U "$DB_USER" -d "$TEST_DB" -tAc \
  "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';")

[ "$TABLE_COUNT" -gt 0 ] || die "Restored DB empty (0 tables)"
log "Check OK — $TABLE_COUNT tables present"

ROW_COUNT=$(PGPASSWORD="${PGPASSWORD}" psql \
  -h "$DB_HOST" -U "$DB_USER" -d "$TEST_DB" -tAc \
  "SELECT COUNT(*) FROM users;" 2>/dev/null || echo "SKIP")

[ "$ROW_COUNT" != "SKIP" ] && log "Table users — $ROW_COUNT rows" || log "Table users not checked"

log "=== RESTORE TEST SUCCESS ==="