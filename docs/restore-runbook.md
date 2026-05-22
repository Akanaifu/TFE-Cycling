# Restore Runbook

Steps to restore a PostgreSQL dump in case of data loss. Keep this file versioned.

1) Identify most recent dump

```bash
ls -lht /var/backups/postgres/daily/
```

2) Stop the API

```bash
docker compose stop api || docker compose stop backend || true
```

3) Restore into production DB (careful: this will overwrite data)

```bash
PGPASSWORD="$POSTGRES_PASSWORD" pg_restore -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB --clean /path/to/dump.dump
```

4) Validate tables

```sql
SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';
```

5) Start services

```bash
docker compose up -d
```

6) Post-restore checks
- Verify user logins
- Run a few business queries
- Check background jobs and syncs
