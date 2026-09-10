# Roadmap V2

## Фаза 0 — спецификация

До написания production-кода согласовать:
- механику баллов;
- механику уровней;
- правила списания;
- награды;
- роли сотрудников;
- обязательный MVP админки;
- сценарии клиента и бариста;
- будущую интеграцию с iiko.

Документы в `docs/` являются source of truth для реализации. Изменение бизнес-правила сначала отражается в спецификации.

## Фаза 1 — foundation

- новая структура проекта;
- config;
- PostgreSQL + Alembic;
- transaction/unit-of-work;
- единый формат ошибок;
- auth foundation;
- audit foundation;
- CI/tests.

## Фаза 2 — customers + staff

- Customer/Identity;
- Staff/Identity;
- RBAC permissions;
- Telegram identity mapping;
- миграционная стратегия V1 -> V2.

## Фаза 3 — loyalty core

- Points ledger;
- balance;
- earning/redemption policies;
- tiers;
- rewards;
- transaction/race-condition tests.

## Фаза 4 — orders

- calculate/preview;
- confirm;
- idempotency;
- cancel/reversal;
- order history;
- audit/events.

## Фаза 5 — thin Telegram bots

Перенести сценарии V1, но удалить из ботов бизнес-решения. Боты получают готовые состояния/расчёты от API.

## Фаза 6 — admin

- клиенты;
- сотрудники;
- заказы;
- ledger;
- tiers;
- rewards;
- settings;
- audit;
- feedback;
- analytics.

## Фаза 7 — campaigns + notifications

- birthday campaign;
- configurable campaigns;
- notification queue;
- Telegram delivery adapter;
- templates.

## Фаза 8 — интеграции

- integration API/auth;
- webhook infrastructure;
- iiko adapter после уточнения доступного API и бизнес-сценария;
- mapping внешних заказов/товаров.

## Фаза 9 — migration/cutover

- импорт пользователей V1;
- сверка балансов;
- импорт истории, где целесообразно;
- dry run;
- backup;
- переключение ботов;
- наблюдение;
- rollback plan.

## Definition of Done для функции

Функция считается законченной, когда:
- правило описано в docs;
- бизнес-логика находится в backend;
- API валидирует вход;
- permissions применены;
- критические изменения аудируются;
- есть unit/integration test;
- UI/бот не дублирует правило;
- migration добавлена, если меняется schema;
- ошибки имеют понятные machine codes.
