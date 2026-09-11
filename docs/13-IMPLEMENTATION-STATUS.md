# V2 Implementation Status

Updated: 2026-09-11
Branch: `v2-implementation`

## Current status

The V2 business core and hardening pass are implemented in code, including customers/staff auth, points ledger, tiers and overrides, orders, refunds, rewards, campaigns, milestones, segments, feedback, notifications, audit, idempotency guards, configuration version snapshots, identification-code fingerprints, explicit refund category allocation and points debt reconciliation.

## Hardening checkpoint

Status: **CODE COMPLETE — REAL TESTS REQUIRED**.

This checkpoint must NOT be treated as production-verified until the following run against a real PostgreSQL instance:

1. Apply the full Alembic chain from `0001_foundation` through the latest migration on an empty database.
2. Upgrade a representative pre-hardening V2 database through all later migrations.
3. Run unit tests and PostgreSQL integration tests.
4. Run concurrent transaction tests for order confirm, refund confirm, points idempotency, identification code generation and reward consumption.
5. Validate rollback/downgrade where downgrade is supported and document destructive downgrades explicitly.
6. Exercise full purchase -> points/reward -> partial refund -> full refund -> debt repayment scenarios.
7. Verify notification outbox retry/idempotency with a test Telegram adapter.
8. Verify multi-location tenant isolation and staff permissions.

Until these tests are executed successfully, production readiness remains provisional.

## Next implementation work

Continue with the remaining roadmap without blocking on the test environment:

- finish thin client/staff Telegram UX;
- close remaining admin flows and analytics endpoints;
- add generic integration API/webhook foundation;
- add V1 migration/cutover tooling and dry-run reconciliation;
- prepare deployment/runbook and real-test checklist.

Real PostgreSQL tests remain a mandatory release gate before cutover.
