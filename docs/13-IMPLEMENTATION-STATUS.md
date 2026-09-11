# V2 Implementation Status

Updated: 2026-09-11
Branch: `v2-implementation`

## Current status

The V2 business core and hardening pass are implemented in code, including customers/staff auth, points ledger, tiers and overrides, orders, refunds, rewards, campaigns, milestones, segments, feedback, notifications, audit, idempotency guards, configuration version snapshots, identification-code fingerprints, explicit refund category allocation and points debt reconciliation.

Subsequent roadmap work now also includes client feedback/preferences UX, admin analytics, explicit override clearing, provider-neutral integration/webhook infrastructure, generic external order processing through the normal loyalty pipeline, V1 migration dry-run/apply tooling, cutover runbook, and a dedicated V2 Docker deployment topology for API, bots, notification worker and migrations.

## Hardening checkpoint

Status: **CODE COMPLETE — REAL TESTS REQUIRED**.

This checkpoint must NOT be treated as production-verified until the following run against a real PostgreSQL instance:

1. Apply the full Alembic chain from `0001_foundation` through the latest migration on an empty database.
2. Upgrade a representative pre-hardening V2 database through all later migrations.
3. Run unit tests and PostgreSQL integration tests.
4. Run concurrent transaction tests for order confirm, refund confirm, points idempotency, identification code generation and reward consumption.
5. Validate rollback/downgrade where downgrade is supported and document destructive downgrades explicitly.
6. Exercise full purchase -> points/reward -> partial refund -> full refund -> debt repayment scenarios.
7. Verify notification outbox claim/lease/retry/idempotency with a test Telegram adapter, including worker crash after send and before completion.
8. Verify multi-location tenant isolation and staff permissions.
9. Exercise generic external-order webhook retries and duplicate external order/event delivery.
10. Build and boot `docker-compose.v2.yml` from a clean environment and verify migration-before-start behavior.

Until these tests are executed successfully, production readiness remains provisional.

## Implemented after checkpoint

- Client bot: feedback flow and marketing notification preferences.
- Admin: analytics summary and explicit audited override clearing.
- Integrations: API-key auth, webhook inbox, provider adapter protocol, external order mapping and generic `order.confirm` adapter.
- Migration: tracked dry-run/apply runs, conflict validation, V1 customer mapping and immutable opening-balance ledger entries.
- Deployment: unprivileged `Dockerfile.v2`, `docker-compose.v2.yml`, `.env.v2.example` and migration gate before API startup.
- Notifications: claim/lease processing so Telegram network calls occur outside database transactions; expired leases are reclaimable after worker crashes.

## Remaining pre-release work

- Real PostgreSQL test execution remains the mandatory release gate.
- Provider-specific adapter (for example iiko) must wait for the exact available API/event contract.
- Final operational observability, backup/restore rehearsal and deployment smoke testing.
- Final cleanup after test failures discovered by the real integration environment.
