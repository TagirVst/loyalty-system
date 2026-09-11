# V2 Operations

## Service probes

- `GET /health` is liveness only. It proves that the API process is running.
- `GET /ready` is readiness. It verifies PostgreSQL connectivity and requires the database to be on the expected Alembic revision.
- `GET /ops/status?staff_session_id=...` is admin-only and exposes organization-scoped notification queue status, overdue work and expired worker leases.

Traffic and dependent services should use `/ready`, not `/health`.

## Backup policy

A production cutover requires a tested PostgreSQL backup and restore procedure.

Recommended minimum:

1. Full custom-format PostgreSQL backup before every schema migration/cutover.
2. Daily automated backups while the system is in production.
3. Retention outside the database host/volume.
4. Encryption and access control for backup files because they contain customer data.
5. Periodic restore rehearsal into an isolated database.

Create a backup from the V2 image/container:

```sh
PGPASSWORD="$POSTGRES_PASSWORD" BACKUP_DIR=/backups ./scripts_v2/backup_postgres.sh
```

The script creates a custom-format dump and validates that `pg_restore` can read its catalog.

## Restore

Restore is intentionally destructive and refuses to run unless explicitly enabled.

```sh
PGPASSWORD="$POSTGRES_PASSWORD" \
ALLOW_DESTRUCTIVE_RESTORE=true \
./scripts_v2/restore_postgres.sh /backups/loyalty_v2_YYYYMMDDTHHMMSSZ.dump
```

Restore must be performed with API, bots and workers stopped. After restore:

1. Verify `alembic_version`.
2. Run `/ready` after API startup.
3. Check customer/points/order/reward counts against the backup manifest or pre-restore reconciliation report.
4. Run one controlled customer identification -> quote -> confirm smoke transaction in the isolated/restored environment.
5. Verify notification worker lease recovery and no duplicate sends in the test adapter.

## Release gates

Production release remains blocked until all of these have been executed in a real PostgreSQL environment:

- full migration chain to latest head;
- PostgreSQL integration test suite;
- concurrency/idempotency tests;
- tenant-isolation tests;
- backup -> destroy isolated DB -> restore -> reconciliation rehearsal;
- `docker-compose.v2.yml` clean boot;
- readiness failure test with database unavailable and with stale Alembic revision.

## Tenant isolation

Every integration/customer/staff operation must resolve organization context from an authenticated principal or integration client. Payload-supplied `organization_id` must not determine authorization. External order locations are explicitly verified against the integration client's organization and active location set before a draft is created.
