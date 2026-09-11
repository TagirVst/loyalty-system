# V2 Cutover Runbook

## Release gate

No production cutover is allowed until the real-test checkpoint in `docs/13-IMPLEMENTATION-STATUS.md` is completed against PostgreSQL.

## 1. Pre-cutover

- freeze V1 loyalty configuration changes;
- take database and bot configuration backups;
- deploy V2 schema to staging from migration `0001` through latest;
- configure production secrets for PIN, identification codes and integration API keys;
- configure organization, locations, tiers, reward definitions, categories and notification templates;
- verify staff terminals and administrator access;
- export V1 customers in the normalized migration format.

## 2. Migration dry run

Run `scripts_v2/migrate_v1.py` without `--apply`.

Required result:
- no duplicate source IDs;
- no duplicate Telegram identities;
- no conflicting phones;
- no invalid birth dates;
- no negative opening balances;
- expected input/valid row counts match the V1 export.

Resolve all conflicts before applying the import. A dry run with errors is not a release candidate.

## 3. Apply migration

Run the same import with explicit `--apply` only after a clean dry run.

Validate:
- imported customer count;
- `legacy_customer_mappings` count;
- total opening balance in mappings;
- total `migration` ledger delta;
- random sample of Telegram identity, phone, birth date and balance values.

Opening balances must be represented by ledger entries, never by direct balance mutation.

## 4. Functional smoke test

For test customers in every location:
- open client bot session;
- generate a 5-digit identification code;
- attach code to an order draft;
- quote and confirm an order;
- earn points;
- redeem points;
- consume a reward;
- issue a partial refund with explicit categories;
- issue a final refund;
- verify points debt if cashback had already been spent;
- verify reward restoration rules;
- verify tier recalculation;
- submit positive and negative feedback;
- verify notification delivery/retry.

## 5. Concurrency gate

Run real concurrent PostgreSQL tests for:
- duplicate order confirm with the same idempotency key;
- duplicate refund confirm;
- simultaneous identification-code generation;
- simultaneous reward consumption;
- simultaneous point adjustment/earn/redeem;
- webhook duplicate delivery.

All financial operations must converge to one committed business result.

## 6. Switch bots

- stop V1 write traffic;
- run final V1 export and reconciliation;
- apply the final delta/import if required;
- switch Telegram bot processes to V2;
- start notification worker;
- verify health and DB connectivity;
- keep V1 data read-only during the observation window.

## 7. Observation

Monitor at minimum:
- API 4xx/5xx rate;
- failed notification outbox rows;
- integration webhook failures;
- points debt creation;
- refund volume;
- duplicate/idempotency conflicts;
- migration/reconciliation totals;
- staff login lockouts.

## 8. Rollback

If a critical issue occurs before substantial V2-only activity:
- stop V2 bot/API write traffic;
- preserve V2 database for investigation;
- restore V1 bot routing;
- do not copy V2 balances back into V1 automatically;
- reconcile all V2 transactions made after cutover before any second attempt.

Once meaningful V2-only financial activity exists, rollback becomes a reconciliation operation rather than a simple database restore.
