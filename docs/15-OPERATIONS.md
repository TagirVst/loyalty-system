# V2 Operations

## Service probes

- `GET /health` is liveness only. It proves that the API process is running.
- `GET /ready` is readiness. It verifies PostgreSQL connectivity and requires the database to be on the expected Alembic revision.
- `GET /ops/status?staff_session_id=...` is admin-only and exposes organization-scoped notification queue status, overdue work and expired worker leases.
- `GET /ops/reconcile?staff_session_id=...` is admin-only and runs organization-scoped financial consistency checks for points account/ledger snapshots and refund/order totals.

Traffic and dependent services should use `/ready`, not `/health`.

## Preflight

Production Compose starts in this order:

`PostgreSQL -> Alembic migrations -> preflight -> API -> bots/workers`.

The preflight command is:

```sh
python scripts_v2/preflight.py
```

It must fail deployment when the database is unreachable, the schema is not at the expected head, production secrets are invalid, `organization_id` is malformed/missing for enabled bots, or SQL echo is enabled in production.

## PostgreSQL release test stack

Run the isolated real-PostgreSQL gate with:

```sh
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from tests
```

The test container first applies the complete Alembic chain and then runs `pytest -q tests_v2`, including tests marked `integration` against PostgreSQL through `LOYALTY_TEST_DATABASE_URL`.

A passing static/unit suite without this stack does **not** satisfy the production release gate.

## Reconciliation gate

Run `/ops/reconcile` before cutover and again after migration/import and after any restore rehearsal. A production cutover requires:

- `ok = true`;
- `issue_count = 0`;
- account balance/debt snapshots matching the latest ledger entries;
- cumulative refund gross/paid/points/qualification not exceeding the source order values.

Any reconciliation issue blocks cutover until investigated. Do not auto-repair financial state from this endpoint.

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
2. Run preflight.
3. Run `/ready` after API startup.
4. Run `/ops/reconcile` and require zero issues.
5. Check customer/points/order/reward counts against the backup manifest or pre-restore reconciliation report.
6. Run one controlled customer identification -> quote -> confirm smoke transaction in the isolated/restored environment.
7. Verify notification worker lease recovery and no duplicate sends in the test adapter.

## Release gates

Production release remains blocked until all of these have been executed in a real PostgreSQL environment:

- full migration chain to latest head;
- PostgreSQL integration test suite using `docker-compose.test.yml`;
- concurrency/idempotency tests;
- tenant-isolation tests;
- reconciliation with zero issues before and after migration/cutover rehearsal;
- backup -> destroy isolated DB -> restore -> reconciliation rehearsal;
- `docker-compose.v2.yml` clean boot including successful preflight;
- readiness failure test with database unavailable and with stale Alembic revision.

## Tenant isolation

Every integration/customer/staff operation must resolve organization context from an authenticated principal or integration client. Payload-supplied `organization_id` must not determine authorization. External order locations are explicitly verified against the integration client's organization and active location set before a draft is created.
