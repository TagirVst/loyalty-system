# Loyalty System V2 — v0.1.0rc1

Дата snapshot: 2026-09-11
Статус: **PRE-RELEASE / RELEASE CANDIDATE**

Этот snapshot содержит полную V2-реализацию в текущем состоянии вместе с миграциями, Telegram-ботами, API, тестами, Docker-конфигурацией, migration/cutover tooling и эксплуатационной документацией.

## Что реализовано

### Архитектура и foundation
- модульный монолит на FastAPI;
- PostgreSQL + SQLAlchemy async;
- Alembic chain `0001` → `0027`;
- Organization → Location tenant model;
- machine-readable domain errors;
- audit log;
- production config validation и preflight;
- liveness `/health` и readiness `/ready`.

### Customers / auth
- Telegram identity;
- обязательные имя, телефон, дата рождения;
- customer sessions с TTL;
- блокировка клиента;
- смена телефона только через Telegram contact текущего пользователя в client bot;
- самостоятельная смена даты рождения только один раз;
- профиль, история, награды, уведомления и feedback.

### Staff
- роли barista/admin;
- привязка сотрудника и terminal к location;
- 6-значный PIN;
- Argon2 + fingerprint/throttle;
- durable failed-login throttling;
- staff sessions;
- permissions/RBAC;
- own-order cancel window 10 минут.

### Loyalty core
- immutable points ledger;
- cached balance + reconciliation;
- points debt для refund, когда cashback уже потрачен;
- 1 point = 1 RUB;
- default redemption limit 30%, временный override до 100%;
- любое списание points отключает cashback на заказ;
- qualification не уменьшается points;
- tiers Standard/Silver/Gold/Platinum;
- data-driven tier thresholds/cashback rates;
- manual tier override;
- inactivity downgrade;
- cashback campaign multipliers;
- reward/campaign stacking rules;
- reward definition snapshots и config versions;
- milestone reward counters и historical snapshots;
- birthday issuance guard per customer/year.

### Orders
- draft → identification → quote → confirm;
- quote TTL и stale detection;
- category counts;
- reward selection;
- cashback/tier calculation;
- immutable loyalty effects snapshot;
- transaction-scoped PostgreSQL advisory idempotency locks;
- idempotency-key reuse protection;
- actor/location/organization scoping.

### Identification
- 5-digit temporary code, TTL 90 seconds;
- plaintext code не хранится в БД;
- HMAC-SHA256 fingerprint;
- один active code на customer;
- collision protection через database constraints/savepoint.

### Refunds
- full и partial refund;
- cumulative proportional allocation;
- explicit category allocation;
- возврат spent points;
- reversal earned cashback;
- points debt при недостаточном балансе;
- qualification reversal + tier recalculation;
- milestone reversal;
- full-refund reward restoration при допустимом lifecycle;
- idempotency guard.

### Rewards / campaigns / segments / feedback
- typed reward definitions;
- campaigns с priorities/stackability/conditions/effects;
- segments;
- birthday jobs;
- feedback 1–5;
- positive external-review offer;
- negative feedback routing to active admin chats;
- admin resolution/audit.

### Notifications
- customer service/marketing preferences;
- templates;
- outbox;
- idempotency;
- claim/lease worker;
- Telegram network call выполняется вне DB transaction;
- retries/backoff;
- recovery expired lease после worker crash.

### Admin/API
- customers/search/card;
- ledger/orders/rewards/feedback/category counters;
- manual points adjustment with reason;
- block/unblock;
- tier/redemption overrides + explicit clear;
- staff/terminal management;
- reward/campaign/category/milestone config;
- segments/feedback settings;
- segment notification enqueue;
- analytics summary;
- operational status;
- reconciliation endpoint.

### Integrations
- provider-neutral integration clients;
- HMAC API-key fingerprints;
- idempotent webhook inbox;
- external order mapping;
- generic `order.confirm` adapter;
- external order проходит через обычный loyalty order pipeline;
- location tenant validation;
- добавлена отдельная спецификация `docs/16-IIKO-INTEGRATION.md` для актуального iikoWeb/решения «Кафе» и iikoCloud/iikoFront integration path;
- в iiko-спецификации зафиксированы новая схема API authorization 2026, mapping organizations/terminal groups/catalog/orders, source-of-truth rules, security, reconciliation и phased implementation plan.

### Migration / cutover
- V1 customer import model;
- dry-run по умолчанию;
- conflict detection по source ID / Telegram / phone;
- immutable ledger opening balance;
- migration run tracking;
- explicit `--apply`;
- cutover runbook и rollback plan.

### Operations / deployment
- unprivileged `Dockerfile.v2`;
- isolated `requirements-v2.txt`;
- `docker-compose.v2.yml`;
- startup chain: PostgreSQL → Alembic → preflight → API → bots/workers;
- `.env.v2.example`;
- PostgreSQL backup/restore scripts;
- destructive restore guard;
- database-name validation;
- reconciliation procedure;
- dedicated PostgreSQL CI/test environment.

## Финальный audit перед RC

Перед созданием snapshot были найдены и исправлены следующие release-блокеры:

- удалены obsolete insecure API routes, доверявшие `organization_id` из request body;
- удалён duplicate `secure_policy_routes`, конфликтовавший с admin customer routes;
- закрыт HTTP bypass проверки телефона — phone change оставлен только через Telegram verified contact flow;
- order/refund idempotency сериализована advisory lock и запрещает reuse ключа для другого объекта;
- reward definition version добавлена в confirmed order effect snapshot;
- усилено tenant scoping критических order/refund запросов;
- исправлен Compose env interpolation для `.env.v2`;
- V2 dependencies отделены от legacy V1 requirements;
- backup/restore автоматически используют `POSTGRES_PASSWORD` как `PGPASSWORD` и проверяют имя БД;
- введённый PIN сотрудника удаляется из Telegram-чата best-effort сразу после считывания;
- версия API/package синхронизирована как `0.1.0rc1`.

## iiko integration documentation

В prerelease включён файл `docs/16-IIKO-INTEGRATION.md`, подготовленный после проверки актуальных на 2026-09-11 материалов iiko.

В нём зафиксировано:

- публичный вариант iiko для формата «Кафе» и роль iikoWeb;
- почему Cloud API нельзя автоматически считать включённым в тариф без проверки entitlement конкретного аккаунта;
- переход iiko в 2026 году на новую developer-app authorization scheme и отказ от legacy auth;
- разграничение iikoCloud API, iikoFront API/plugin и iikoConnector;
- mapping iiko organization/terminal group/order/product/customer → наши Organization/Location/ExternalOrderMapping/SaleCategory/Customer mappings;
- модель, где iiko является source of truth для POS-факта продажи, а Loyalty System V2 — source of truth для points/tiers/rewards/campaigns/refunds/audit;
- Cloud-only integration path для organizations, terminal groups, menu/catalog, stop lists и внешних заказов;
- отдельный native iikoFront checkout path для применения нашей лояльности к обычным кассовым продажам;
- правила idempotency, refund, reconciliation, retries, secrets и logging;
- поэтапный план `IIKO-0` → `IIKO-5`;
- список вопросов, которые нужно подтвердить у iiko/партнёра перед production connector implementation.

## Verification

Автоматический workflow `.github/workflows/v2-prerelease.yml` поднимает настоящий PostgreSQL 16 и выполняет:

1. установку V2 dependencies и package;
2. Python compileall;
3. полный `alembic upgrade head`;
4. `pytest -q tests_v2` включая PostgreSQL integration schema checks.

Последний кодовый snapshot перед добавлением iiko-документации: **123 passed, 2 deprecation warnings, 0 failures**. Документационные изменения не меняют runtime/schema, но release branch всё равно прогоняется CI после обновления snapshot.

## Что сознательно НЕ считается завершённым в v0.1 RC

- provider-specific iiko adapter: архитектура и точный план уже описаны в `docs/16-IIKO-INTEGRATION.md`, но production implementation требует credentials, фактических scopes и подтверждения commercial/API entitlement конкретного iikoWeb аккаунта;
- native iikoFront loyalty connector/plugin: нужно подтвердить рекомендуемый iiko механизм для внешней loyalty в обычном POS checkout;
- production cutover на реальных данных: нужен V1 dry-run и reconciliation фактической базы;
- backup→destroy→restore rehearsal на отдельной production-like БД;
- полноценные concurrency/load tests под реальной параллельной нагрузкой;
- Telegram delivery остаётся at-least-once: при падении worker после успешной отправки, но до фиксации результата, редкий duplicate теоретически возможен;
- отдельная immutable history table для всех campaign revisions пока отсутствует: confirmed order хранит version + monetary effects, но не полную историческую копию каждой Campaign revision;
- staff bot FSM хранится в памяти процесса: после restart незавершённый UI flow нужно начать заново;
- автоматический session timeout/end-of-shift policy для staff требует отдельной настройки/задачи;
- полноценный визуальный admin frontend не входит в RC: реализован admin backend/API;
- notification template CRUD UI/API и расширенные pagination/reporting можно добавить после RC;
- production monitoring/alerting (Prometheus/Sentry и т.п.) не подключён внешним провайдером.

## Запуск

1. Скопировать `.env.v2.example` → `.env.v2`.
2. Заменить пароли/secrets, указать Telegram bot tokens и organization UUID.
3. Запустить:

```sh
docker compose -f docker-compose.v2.yml up --build -d
```

4. Проверить:

```sh
curl -f http://localhost:8000/ready
```

5. Перед cutover выполнить admin reconciliation и backup согласно `docs/15-OPERATIONS.md` и `docs/14-CUTOVER-RUNBOOK.md`.

## PostgreSQL test run

```sh
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from tests
```

## Production status

`v0.1.0rc1` — это prerelease, а не объявление production GA. Разрешение на production cutover требует зелёного PostgreSQL CI для release snapshot, реального V1 migration dry-run, backup/restore rehearsal и финальной reconciliation реальных данных.
