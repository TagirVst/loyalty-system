# Database Schema V2

## 1. Цель

Документ фиксирует физическую PostgreSQL-схему Loyalty V2 настолько подробно, чтобы по нему можно было писать Alembic migrations, SQLAlchemy models и repository layer без повторного проектирования.

Принципы:
- PostgreSQL;
- UUID как публично безопасный internal identifier для основных сущностей;
- денежные значения — `BIGINT` в minor units, без float;
- points — `BIGINT`, целые;
- timestamps — `TIMESTAMPTZ` в UTC;
- timezone хранится отдельно на Organization/Location;
- mutable operational entities используют `version` для optimistic concurrency там, где это полезно;
- финансовые/аудитные журналы append-only;
- soft-delete используется только там, где физическое удаление опасно;
- PII и секреты отделены от audit payload;
- все FK и uniqueness учитывают `organization_id`.

## 2. Extensions

Рекомендуемые PostgreSQL extensions:

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
```

UUID генерируются приложением или `gen_random_uuid()`.

## 3. organizations

```text
id                  UUID PK
code                CITEXT NOT NULL
name                TEXT NOT NULL
currency_code       CHAR(3) NOT NULL DEFAULT 'RUB'
timezone             TEXT NOT NULL DEFAULT 'Europe/Moscow'
status               TEXT NOT NULL DEFAULT 'active'
created_at           TIMESTAMPTZ NOT NULL
updated_at           TIMESTAMPTZ NOT NULL
version              BIGINT NOT NULL DEFAULT 1
```

Constraints:
- UNIQUE(code)
- CHECK status IN ('active','suspended','archived')
- CHECK currency_code ~ '^[A-Z]{3}$'

V2 фактически использует одну Organization, но все tenant-owned сущности получают `organization_id`.

## 4. locations

```text
id                  UUID PK
organization_id     UUID NOT NULL FK organizations(id)
code                CITEXT NOT NULL
name                TEXT NOT NULL
address             TEXT NULL
timezone             TEXT NULL
status               TEXT NOT NULL DEFAULT 'active'
created_at           TIMESTAMPTZ NOT NULL
updated_at           TIMESTAMPTZ NOT NULL
version              BIGINT NOT NULL DEFAULT 1
```

Constraints:
- UNIQUE(organization_id, code)
- CHECK status IN ('active','inactive','archived')

Indexes:
- (organization_id, status)

## 5. customers

```text
id                       UUID PK
organization_id          UUID NOT NULL FK organizations(id)
telegram_user_id         BIGINT NOT NULL
first_name               TEXT NOT NULL
phone_e164               TEXT NOT NULL
birth_date               DATE NOT NULL
birth_date_change_count  SMALLINT NOT NULL DEFAULT 0
status                   TEXT NOT NULL DEFAULT 'active'
blocked_at               TIMESTAMPTZ NULL
blocked_reason           TEXT NULL
marketing_opt_in         BOOLEAN NOT NULL DEFAULT true
created_at               TIMESTAMPTZ NOT NULL
updated_at               TIMESTAMPTZ NOT NULL
version                  BIGINT NOT NULL DEFAULT 1
```

Constraints:
- UNIQUE(organization_id, telegram_user_id)
- UNIQUE(organization_id, phone_e164)
- CHECK birth_date_change_count BETWEEN 0 AND 1
- CHECK status IN ('active','blocked','archived')
- CHECK phone_e164 ~ '^\+[1-9][0-9]{7,14}$'

Indexes:
- (organization_id, status)
- (organization_id, created_at DESC)
- (organization_id, phone_e164)

Физическое удаление customer не используется, если есть финансовая история.

## 6. customer_profile_change_log

```text
id                  UUID PK
organization_id     UUID NOT NULL
customer_id         UUID NOT NULL FK customers(id)
field_name          TEXT NOT NULL
old_value_masked    TEXT NULL
new_value_masked    TEXT NULL
actor_type          TEXT NOT NULL
actor_id            UUID NULL
created_at          TIMESTAMPTZ NOT NULL
```

Для birth_date отдельный business guard ограничивает самостоятельное изменение одним разом.

## 7. staff

```text
id                  UUID PK
organization_id     UUID NOT NULL FK organizations(id)
location_id         UUID NOT NULL FK locations(id)
name                TEXT NOT NULL
role_code           TEXT NOT NULL
pin_hash            TEXT NULL
status              TEXT NOT NULL DEFAULT 'active'
created_at          TIMESTAMPTZ NOT NULL
updated_at          TIMESTAMPTZ NOT NULL
version             BIGINT NOT NULL DEFAULT 1
```

Constraints:
- CHECK role_code IN ('barista','admin') в V2; future roles через role table допускаются позже
- CHECK status IN ('active','inactive','archived')
- barista MUST have pin_hash

PIN uniqueness нельзя надёжно проверить по hash при salted Argon2. Поэтому вводится отдельный blind index.

## 8. staff_pin_index

```text
staff_id             UUID PK FK staff(id)
organization_id      UUID NOT NULL
pin_fingerprint      BYTEA NOT NULL
created_at           TIMESTAMPTZ NOT NULL
```

`pin_fingerprint = HMAC(server_pepper, normalized_6_digit_pin)`.

Constraints:
- UNIQUE(organization_id, pin_fingerprint)

Сам PIN хранится только в `staff.pin_hash` как Argon2id/bcrypt hash. Fingerprint нужен только для uniqueness/lookup и не заменяет password hash.

## 9. staff_terminals

```text
id                   UUID PK
organization_id      UUID NOT NULL
location_id          UUID NOT NULL FK locations(id)
telegram_user_id     BIGINT NULL
telegram_chat_id     BIGINT NOT NULL
name                 TEXT NULL
status               TEXT NOT NULL DEFAULT 'active'
last_seen_at         TIMESTAMPTZ NULL
created_at           TIMESTAMPTZ NOT NULL
updated_at           TIMESTAMPTZ NOT NULL
version              BIGINT NOT NULL DEFAULT 1
```

Constraints:
- UNIQUE(organization_id, telegram_chat_id)
- CHECK status IN ('active','revoked','archived')

## 10. staff_sessions

```text
id                   UUID PK
organization_id      UUID NOT NULL
staff_id             UUID NOT NULL FK staff(id)
terminal_id          UUID NOT NULL FK staff_terminals(id)
location_id          UUID NOT NULL FK locations(id)
started_at           TIMESTAMPTZ NOT NULL
ended_at             TIMESTAMPTZ NULL
ended_reason         TEXT NULL
created_by_method    TEXT NOT NULL DEFAULT 'pin'
```

Partial unique index:

```sql
UNIQUE (terminal_id) WHERE ended_at IS NULL
```

Дополнительно рекомендуется не разрешать сотруднику несколько активных staff sessions одновременно, если бизнес не потребует обратное:

```sql
UNIQUE (staff_id) WHERE ended_at IS NULL
```

## 11. admin_identities

```text
id                   UUID PK
organization_id      UUID NOT NULL
staff_id             UUID NOT NULL FK staff(id)
provider             TEXT NOT NULL
provider_subject     TEXT NOT NULL
status               TEXT NOT NULL DEFAULT 'active'
created_at           TIMESTAMPTZ NOT NULL
```

Constraints:
- UNIQUE(organization_id, provider, provider_subject)

V2 provider = `telegram`. Позже OAuth/SSO/Password могут добавляться без изменения staff.

## 12. roles / permissions

Даже при двух ролях права оформляются capability-based.

### roles
```text
id                   UUID PK
organization_id      UUID NOT NULL
code                 CITEXT NOT NULL
name                 TEXT NOT NULL
is_system            BOOLEAN NOT NULL DEFAULT false
created_at           TIMESTAMPTZ NOT NULL
```

UNIQUE(organization_id, code)

### permissions
```text
code                 CITEXT PK
name                 TEXT NOT NULL
```

### role_permissions
```text
role_id              UUID NOT NULL FK roles(id)
permission_code      CITEXT NOT NULL FK permissions(code)
PRIMARY KEY(role_id, permission_code)
```

### staff_roles
```text
staff_id             UUID NOT NULL FK staff(id)
role_id              UUID NOT NULL FK roles(id)
PRIMARY KEY(staff_id, role_id)
```

`staff.role_code` можно убрать после полного перехода на role tables; для initial migration допустимо держать только role tables. Предпочтительно сразу использовать tables и не дублировать роль.

## 13. loyalty_tiers

```text
id                    UUID PK
organization_id       UUID NOT NULL
code                  CITEXT NOT NULL
name                  TEXT NOT NULL
sort_order            INTEGER NOT NULL
minimum_spend_minor   BIGINT NOT NULL
cashback_bps          INTEGER NOT NULL
client_description    TEXT NULL
status                TEXT NOT NULL DEFAULT 'active'
created_at            TIMESTAMPTZ NOT NULL
updated_at            TIMESTAMPTZ NOT NULL
version               BIGINT NOT NULL DEFAULT 1
```

`cashback_bps`: basis points, 3% = 300, 7% = 700.

Constraints:
- UNIQUE(organization_id, code)
- UNIQUE(organization_id, sort_order)
- CHECK minimum_spend_minor >= 0
- CHECK cashback_bps BETWEEN 0 AND 10000
- CHECK status IN ('active','inactive','archived')

Стартовые данные:
- Standard: 0 ₽, 3%
- Silver: 15 000 ₽, 5%
- Gold: 40 000 ₽, 7%
- Platinum: 80 000 ₽, 10%

Проверка строго возрастающих thresholds выполняется application service + DB locking при изменении набора уровней.

## 14. customer_loyalty_state

```text
customer_id                    UUID PK FK customers(id)
organization_id                UUID NOT NULL
automatic_tier_id              UUID NOT NULL FK loyalty_tiers(id)
effective_tier_id              UUID NOT NULL FK loyalty_tiers(id)
qualification_spend_minor      BIGINT NOT NULL DEFAULT 0
lifetime_purchase_minor        BIGINT NOT NULL DEFAULT 0
last_purchase_at               TIMESTAMPTZ NULL
inactivity_penalty_steps       INTEGER NOT NULL DEFAULT 0
next_inactivity_check_at       TIMESTAMPTZ NULL
updated_at                     TIMESTAMPTZ NOT NULL
version                        BIGINT NOT NULL DEFAULT 1
```

Constraints:
- CHECK qualification_spend_minor >= 0
- CHECK lifetime_purchase_minor >= 0
- CHECK inactivity_penalty_steps >= 0

При новой покупке inactivity penalty сбрасывается и automatic tier немедленно пересчитывается по qualification spend согласно принятой политике.

## 15. customer_tier_overrides

```text
id                    UUID PK
organization_id       UUID NOT NULL
customer_id           UUID NOT NULL FK customers(id)
tier_id               UUID NOT NULL FK loyalty_tiers(id)
starts_at             TIMESTAMPTZ NOT NULL
ends_at               TIMESTAMPTZ NULL
reason                TEXT NOT NULL
created_by_staff_id   UUID NOT NULL FK staff(id)
revoked_at            TIMESTAMPTZ NULL
revoked_by_staff_id   UUID NULL FK staff(id)
created_at            TIMESTAMPTZ NOT NULL
```

Index:
- (customer_id, starts_at DESC)

Business invariant: одновременно не более одного effective override.

## 16. customer_redemption_overrides

```text
id                    UUID PK
organization_id       UUID NOT NULL
customer_id           UUID NOT NULL FK customers(id)
limit_bps             INTEGER NOT NULL
starts_at             TIMESTAMPTZ NOT NULL
ends_at               TIMESTAMPTZ NOT NULL
reason                TEXT NOT NULL
created_by_staff_id   UUID NOT NULL FK staff(id)
revoked_at            TIMESTAMPTZ NULL
created_at            TIMESTAMPTZ NOT NULL
```

Constraints:
- CHECK limit_bps BETWEEN 0 AND 10000
- CHECK ends_at > starts_at

Временность обязательна.

## 17. tier_history

```text
id                    UUID PK
organization_id       UUID NOT NULL
customer_id           UUID NOT NULL
tier_id               UUID NOT NULL
source                TEXT NOT NULL
reason_code           TEXT NULL
qualification_spend_minor BIGINT NOT NULL
occurred_at           TIMESTAMPTZ NOT NULL
correlation_id        UUID NULL
```

Append-only.

## 18. points_accounts

```text
customer_id            UUID PK FK customers(id)
organization_id        UUID NOT NULL
balance_points         BIGINT NOT NULL DEFAULT 0
updated_at             TIMESTAMPTZ NOT NULL
version                BIGINT NOT NULL DEFAULT 1
```

Constraint:
- CHECK balance_points >= 0

Это кэш/aggregate state. Источник финансовой истины — ledger.

## 19. points_ledger

```text
id                     UUID PK
organization_id        UUID NOT NULL
customer_id            UUID NOT NULL FK customers(id)
entry_type             TEXT NOT NULL
delta_points           BIGINT NOT NULL
balance_after          BIGINT NOT NULL
order_id               UUID NULL
refund_id              UUID NULL
reward_id              UUID NULL
campaign_id            UUID NULL
actor_staff_id         UUID NULL
reason                 TEXT NULL
idempotency_key        TEXT NULL
correlation_id         UUID NOT NULL
expires_at             TIMESTAMPTZ NULL
created_at             TIMESTAMPTZ NOT NULL
```

Entry types initial:
- earn
- redeem
- refund_restore
- earn_reversal
- manual_credit
- manual_debit
- campaign_credit
- expiration
- migration

Constraints:
- delta_points <> 0
- balance_after >= 0

Indexes:
- (customer_id, created_at DESC)
- (organization_id, created_at DESC)
- (order_id)
- (refund_id)
- (correlation_id)

UNIQUE where idempotency_key is not null:
- (organization_id, idempotency_key)

Ledger rows never update/delete in normal operation.

## 20. point_lots — future expiry support

Чтобы позднее включить срок действия баллов без redesign, рекомендуется заложить lots сразу.

```text
id                     UUID PK
organization_id        UUID NOT NULL
customer_id            UUID NOT NULL
source_ledger_id       UUID NOT NULL FK points_ledger(id)
original_points        BIGINT NOT NULL
remaining_points       BIGINT NOT NULL
expires_at             TIMESTAMPTZ NULL
created_at             TIMESTAMPTZ NOT NULL
```

Constraints:
- CHECK original_points > 0
- CHECK remaining_points BETWEEN 0 AND original_points

Если expiry отключён, `expires_at NULL`.
При redemption будущая policy может потреблять lots FIFO по expiration.

## 21. identification_sessions

```text
id                     UUID PK
organization_id        UUID NOT NULL
customer_id            UUID NOT NULL FK customers(id)
method                 TEXT NOT NULL
code_hash              BYTEA NULL
code_fingerprint       BYTEA NULL
status                 TEXT NOT NULL DEFAULT 'active'
expires_at             TIMESTAMPTZ NOT NULL
consumed_at            TIMESTAMPTZ NULL
consumed_by_order_id   UUID NULL
created_at             TIMESTAMPTZ NOT NULL
```

V2 method = `numeric_code`.

Constraints:
- CHECK status IN ('active','consumed','expired','revoked')

Partial indexes:
- UNIQUE(customer_id) WHERE status='active'
- UNIQUE(organization_id, code_fingerprint) WHERE status='active'

Код живёт 90 sec. В БД не хранится plaintext code.

## 22. order_categories

```text
id                     UUID PK
organization_id        UUID NOT NULL
code                   CITEXT NOT NULL
name                   TEXT NOT NULL
sort_order             INTEGER NOT NULL DEFAULT 0
status                 TEXT NOT NULL DEFAULT 'active'
unit_semantics         TEXT NOT NULL DEFAULT 'count'
created_at             TIMESTAMPTZ NOT NULL
updated_at             TIMESTAMPTZ NOT NULL
version                BIGINT NOT NULL DEFAULT 1
```

Constraints:
- UNIQUE(organization_id, code)
- CHECK status IN ('active','inactive','archived')

## 23. orders

```text
id                         UUID PK
organization_id            UUID NOT NULL
location_id                UUID NOT NULL FK locations(id)
customer_id                UUID NOT NULL FK customers(id)
staff_id                   UUID NULL FK staff(id)
staff_session_id           UUID NULL FK staff_sessions(id)
source                     TEXT NOT NULL
external_provider          TEXT NULL
external_order_id          TEXT NULL
idempotency_key            TEXT NOT NULL
status                     TEXT NOT NULL
gross_amount_minor         BIGINT NOT NULL
reward_discount_minor      BIGINT NOT NULL DEFAULT 0
points_redeemed            BIGINT NOT NULL DEFAULT 0
points_value_minor         BIGINT NOT NULL DEFAULT 0
paid_amount_minor          BIGINT NOT NULL
cashback_base_minor        BIGINT NOT NULL
points_earned              BIGINT NOT NULL DEFAULT 0
qualification_amount_minor BIGINT NOT NULL
currency_code              CHAR(3) NOT NULL DEFAULT 'RUB'
quote_snapshot             JSONB NOT NULL
confirmed_at               TIMESTAMPTZ NULL
cancelled_at               TIMESTAMPTZ NULL
created_at                 TIMESTAMPTZ NOT NULL
updated_at                 TIMESTAMPTZ NOT NULL
version                    BIGINT NOT NULL DEFAULT 1
```

Constraints:
- UNIQUE(organization_id, idempotency_key)
- UNIQUE(organization_id, external_provider, external_order_id) WHERE external_order_id IS NOT NULL
- CHECK source IN ('manual','pos','migration','internal')
- CHECK status IN ('draft','quoted','confirmed','partially_refunded','refunded','cancelled','failed')
- CHECK gross_amount_minor >= 0
- CHECK reward_discount_minor >= 0
- CHECK points_redeemed >= 0
- CHECK paid_amount_minor >= 0
- CHECK points_earned >= 0
- CHECK qualification_amount_minor >= 0

`quote_snapshot` хранит explainability/versioned policy snapshot, не используется как единственная финансовая истина.

Indexes:
- (organization_id, created_at DESC)
- (customer_id, confirmed_at DESC)
- (staff_id, confirmed_at DESC)
- (location_id, confirmed_at DESC)
- (status, created_at DESC)

## 24. order_category_metrics

```text
order_id              UUID NOT NULL FK orders(id)
category_id           UUID NOT NULL FK order_categories(id)
quantity              INTEGER NOT NULL
PRIMARY KEY(order_id, category_id)
```

CHECK quantity >= 0.

## 25. order_quotes

Если quote нужно хранить отдельно от order snapshot:

```text
id                    UUID PK
organization_id       UUID NOT NULL
order_id              UUID NOT NULL FK orders(id)
version_no            INTEGER NOT NULL
input_hash            BYTEA NOT NULL
result_json           JSONB NOT NULL
expires_at            TIMESTAMPTZ NOT NULL
created_at            TIMESTAMPTZ NOT NULL
```

UNIQUE(order_id, version_no).

Confirm принимает quote id/version и повторно валидирует актуальность.

## 26. refunds

```text
id                       UUID PK
organization_id          UUID NOT NULL
order_id                 UUID NOT NULL FK orders(id)
location_id              UUID NOT NULL
actor_staff_id           UUID NULL
source                   TEXT NOT NULL
external_provider        TEXT NULL
external_refund_id       TEXT NULL
idempotency_key          TEXT NOT NULL
status                   TEXT NOT NULL
refund_amount_minor      BIGINT NOT NULL
points_restored          BIGINT NOT NULL DEFAULT 0
earned_points_reversed   BIGINT NOT NULL DEFAULT 0
qualification_reversed_minor BIGINT NOT NULL DEFAULT 0
reason                   TEXT NULL
calculation_snapshot     JSONB NOT NULL
created_at               TIMESTAMPTZ NOT NULL
confirmed_at             TIMESTAMPTZ NULL
```

Constraints:
- UNIQUE(organization_id, idempotency_key)
- UNIQUE(organization_id, external_provider, external_refund_id) WHERE external_refund_id IS NOT NULL
- CHECK refund_amount_minor > 0
- CHECK status IN ('pending','confirmed','failed','cancelled')

Indexes:
- (order_id, created_at DESC)
- (organization_id, created_at DESC)

Cumulative confirmed refunds <= refundable order amount проверяется transactional service с row lock на order.

## 27. refund_category_metrics

```text
refund_id             UUID NOT NULL FK refunds(id)
category_id           UUID NOT NULL FK order_categories(id)
quantity              INTEGER NOT NULL
PRIMARY KEY(refund_id, category_id)
```

CHECK quantity >= 0.

## 28. reward_definitions

```text
id                     UUID PK
organization_id        UUID NOT NULL
code                   CITEXT NOT NULL
name                   TEXT NOT NULL
description            TEXT NULL
reward_type            TEXT NOT NULL
config_json            JSONB NOT NULL
validity_seconds       BIGINT NULL
allow_multiple         BOOLEAN NOT NULL DEFAULT true
status                 TEXT NOT NULL DEFAULT 'active'
created_at             TIMESTAMPTZ NOT NULL
updated_at             TIMESTAMPTZ NOT NULL
version                BIGINT NOT NULL DEFAULT 1
```

Constraints:
- UNIQUE(organization_id, code)
- CHECK status IN ('active','inactive','archived')

`config_json` валидируется typed schema по reward_type.

## 29. customer_rewards

```text
id                     UUID PK
organization_id        UUID NOT NULL
customer_id            UUID NOT NULL
reward_definition_id   UUID NOT NULL
source_type            TEXT NOT NULL
source_id              UUID NULL
quantity_issued        INTEGER NOT NULL
quantity_remaining     INTEGER NOT NULL
issued_at              TIMESTAMPTZ NOT NULL
expires_at             TIMESTAMPTZ NULL
status                 TEXT NOT NULL DEFAULT 'active'
issuance_key            TEXT NULL
created_at             TIMESTAMPTZ NOT NULL
```

Constraints:
- CHECK quantity_issued > 0
- CHECK quantity_remaining BETWEEN 0 AND quantity_issued
- UNIQUE(organization_id, issuance_key) WHERE issuance_key IS NOT NULL

Indexes:
- (customer_id, status, expires_at)

Birthday yearly protection реализуется issuance_key типа `birthday:{customer_id}:{year}:{campaign_id}`.

## 30. reward_redemptions

```text
id                     UUID PK
organization_id        UUID NOT NULL
customer_reward_id     UUID NOT NULL FK customer_rewards(id)
order_id               UUID NOT NULL FK orders(id)
quantity               INTEGER NOT NULL
discount_minor         BIGINT NOT NULL DEFAULT 0
created_at             TIMESTAMPTZ NOT NULL
reversed_at            TIMESTAMPTZ NULL
refund_id              UUID NULL
```

CHECK quantity > 0.

## 31. campaigns

```text
id                     UUID PK
organization_id        UUID NOT NULL
code                   CITEXT NOT NULL
name                   TEXT NOT NULL
status                 TEXT NOT NULL
priority               INTEGER NOT NULL DEFAULT 0
stackable              BOOLEAN NOT NULL DEFAULT true
exclusivity_group      TEXT NULL
starts_at              TIMESTAMPTZ NULL
ends_at                TIMESTAMPTZ NULL
audience_rule_json     JSONB NOT NULL DEFAULT '{}'
order_rule_json        JSONB NOT NULL DEFAULT '{}'
effect_json            JSONB NOT NULL
location_scope_json    JSONB NOT NULL DEFAULT '{}'
created_by_staff_id    UUID NOT NULL
created_at             TIMESTAMPTZ NOT NULL
updated_at             TIMESTAMPTZ NOT NULL
version                BIGINT NOT NULL DEFAULT 1
```

Constraints:
- UNIQUE(organization_id, code)
- CHECK status IN ('draft','scheduled','active','paused','finished','archived')
- CHECK ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at

Rules/effects проходят typed validation, arbitrary executable code запрещён.

## 32. campaign_applications

```text
id                     UUID PK
organization_id        UUID NOT NULL
campaign_id            UUID NOT NULL FK campaigns(id)
customer_id            UUID NOT NULL
order_id               UUID NULL
result_json             JSONB NOT NULL
created_at             TIMESTAMPTZ NOT NULL
correlation_id          UUID NOT NULL
```

Нужно для explainability/analytics и ограничения частоты применения.

## 33. segments

```text
id                     UUID PK
organization_id        UUID NOT NULL
code                   CITEXT NOT NULL
name                   TEXT NOT NULL
segment_type           TEXT NOT NULL
rule_json              JSONB NULL
status                 TEXT NOT NULL DEFAULT 'active'
created_at             TIMESTAMPTZ NOT NULL
updated_at             TIMESTAMPTZ NOT NULL
version                BIGINT NOT NULL DEFAULT 1
```

CHECK segment_type IN ('dynamic','manual').
UNIQUE(organization_id, code).

### segment_members
```text
segment_id             UUID NOT NULL FK segments(id)
customer_id            UUID NOT NULL FK customers(id)
added_at               TIMESTAMPTZ NOT NULL
added_by_staff_id      UUID NULL
PRIMARY KEY(segment_id, customer_id)
```

Используется только для manual segment или materialized cache.

## 34. notification_preferences

```text
customer_id            UUID PK
organization_id        UUID NOT NULL
transactional_enabled  BOOLEAN NOT NULL DEFAULT true
marketing_enabled      BOOLEAN NOT NULL DEFAULT true
updated_at              TIMESTAMPTZ NOT NULL
```

Критические сервисные сообщения могут иметь отдельную policy и не зависеть от marketing opt-out.

## 35. notifications

```text
id                     UUID PK
organization_id        UUID NOT NULL
customer_id            UUID NULL
channel                TEXT NOT NULL
template_code          TEXT NULL
payload_json           JSONB NOT NULL
status                 TEXT NOT NULL
scheduled_at           TIMESTAMPTZ NULL
sent_at                TIMESTAMPTZ NULL
failed_at              TIMESTAMPTZ NULL
provider_message_id    TEXT NULL
attempt_count          INTEGER NOT NULL DEFAULT 0
idempotency_key        TEXT NULL
created_at             TIMESTAMPTZ NOT NULL
```

Indexes:
- (status, scheduled_at)
- (customer_id, created_at DESC)

UNIQUE(organization_id, idempotency_key) WHERE idempotency_key IS NOT NULL.

## 36. mailings

```text
id                     UUID PK
organization_id        UUID NOT NULL
name                   TEXT NOT NULL
segment_id             UUID NULL
message_json           JSONB NOT NULL
status                 TEXT NOT NULL
scheduled_at           TIMESTAMPTZ NULL
created_by_staff_id    UUID NOT NULL
created_at             TIMESTAMPTZ NOT NULL
updated_at             TIMESTAMPTZ NOT NULL
```

Statuses: draft/scheduled/sending/completed/cancelled/failed.

## 37. feedback

```text
id                     UUID PK
organization_id        UUID NOT NULL
customer_id            UUID NOT NULL
order_id               UUID NULL
location_id            UUID NULL
rating                 SMALLINT NOT NULL
text                   TEXT NULL
status                 TEXT NOT NULL DEFAULT 'new'
assigned_staff_id      UUID NULL
internal_note          TEXT NULL
created_at             TIMESTAMPTZ NOT NULL
resolved_at            TIMESTAMPTZ NULL
```

Constraints:
- CHECK rating BETWEEN 1 AND 5
- CHECK status IN ('new','in_progress','resolved','archived')

## 38. integrations

```text
id                     UUID PK
organization_id        UUID NOT NULL
provider_code          CITEXT NOT NULL
name                   TEXT NOT NULL
status                 TEXT NOT NULL
config_json            JSONB NOT NULL DEFAULT '{}'
secret_ref             TEXT NULL
created_at             TIMESTAMPTZ NOT NULL
updated_at             TIMESTAMPTZ NOT NULL
version                BIGINT NOT NULL DEFAULT 1
```

Secrets не хранятся в plain JSON. `secret_ref` указывает на secret manager/env-backed storage abstraction.

UNIQUE(organization_id, provider_code, name).

## 39. external_mappings

```text
id                     UUID PK
organization_id        UUID NOT NULL
integration_id         UUID NOT NULL FK integrations(id)
entity_type            TEXT NOT NULL
internal_id            UUID NOT NULL
external_id            TEXT NOT NULL
location_id            UUID NULL
created_at             TIMESTAMPTZ NOT NULL
```

Constraints:
- UNIQUE(integration_id, entity_type, external_id)
- UNIQUE(integration_id, entity_type, internal_id)

## 40. audit_log

```text
id                     UUID PK
organization_id        UUID NOT NULL
actor_type             TEXT NOT NULL
actor_id               UUID NULL
action                 TEXT NOT NULL
entity_type            TEXT NOT NULL
entity_id              UUID NULL
reason                 TEXT NULL
safe_before_json       JSONB NULL
safe_after_json        JSONB NULL
metadata_json          JSONB NOT NULL DEFAULT '{}'
correlation_id         UUID NULL
created_at             TIMESTAMPTZ NOT NULL
```

Append-only.

Indexes:
- (organization_id, created_at DESC)
- (entity_type, entity_id, created_at DESC)
- (actor_id, created_at DESC)
- (correlation_id)

Запрещено помещать PIN, pin_hash, tokens, raw secrets, полный auth payload.

## 41. outbox_events

```text
id                     UUID PK
organization_id        UUID NULL
aggregate_type         TEXT NOT NULL
aggregate_id           UUID NULL
event_type             TEXT NOT NULL
payload_json           JSONB NOT NULL
occurred_at            TIMESTAMPTZ NOT NULL
available_at           TIMESTAMPTZ NOT NULL
published_at           TIMESTAMPTZ NULL
attempt_count          INTEGER NOT NULL DEFAULT 0
last_error             TEXT NULL
```

Index:
- (published_at, available_at)

Outbox insert выполняется в той же transaction, что и domain change.

## 42. idempotency_records

Для API commands, которым недостаточно entity unique key:

```text
id                     UUID PK
organization_id        UUID NOT NULL
scope                  TEXT NOT NULL
idempotency_key        TEXT NOT NULL
request_hash           BYTEA NOT NULL
response_status        INTEGER NULL
response_json          JSONB NULL
resource_type          TEXT NULL
resource_id            UUID NULL
created_at             TIMESTAMPTZ NOT NULL
expires_at             TIMESTAMPTZ NULL
```

UNIQUE(organization_id, scope, idempotency_key).

Повтор того же key с другим request_hash → conflict.

## 43. system_settings

```text
id                     UUID PK
organization_id        UUID NOT NULL
key                    CITEXT NOT NULL
value_json             JSONB NOT NULL
version                INTEGER NOT NULL
valid_from             TIMESTAMPTZ NOT NULL
valid_to               TIMESTAMPTZ NULL
created_by_staff_id    UUID NULL
created_at             TIMESTAMPTZ NOT NULL
```

UNIQUE(organization_id, key, version).

Настройки versioned. Старые операции сохраняют policy snapshot/version.

Initial settings:
- redemption_limit_bps = 3000
- identification_code_ttl_seconds = 90
- barista_cancel_window_seconds = 600
- inactivity_period_months = 12
- cashback_rounding = floor
- point_currency_minor = 100 для 1 point = 1 RUB при RUB minor unit = kopek
- point_expiry_enabled = false

## 44. birthdate_reward_issuance guard

Хотя birthday reward использует `customer_rewards.issuance_key`, для аналитики/жёсткой гарантии можно иметь отдельную таблицу:

```text
organization_id        UUID NOT NULL
customer_id            UUID NOT NULL
campaign_id            UUID NOT NULL
year_key               INTEGER NOT NULL
customer_reward_id     UUID NULL
issued_at               TIMESTAMPTZ NOT NULL
PRIMARY KEY(organization_id, customer_id, campaign_id, year_key)
```

Это защищает от повторной выдачи при смене birth_date.

## 45. approval_requests — future-ready

Механизм dual approval пока выключен, но схема может быть добавлена сразу или отдельной migration позже.

```text
id                     UUID PK
organization_id        UUID NOT NULL
action_type            TEXT NOT NULL
requested_by_staff_id  UUID NOT NULL
payload_json           JSONB NOT NULL
status                 TEXT NOT NULL
approved_by_staff_id   UUID NULL
created_at             TIMESTAMPTZ NOT NULL
resolved_at            TIMESTAMPTZ NULL
```

Не обязателен для первого production release.

## 46. Каскады и удаление

Правило по умолчанию: `ON DELETE RESTRICT` для финансово значимых FK.

Допускается `ON DELETE CASCADE` только для чисто зависимых технических child rows, например:
- role_permissions при удалении role до production history;
- segment_members;
- draft-only temporary data.

Orders, ledger, refunds, audit, reward redemptions физически не удаляются.

Organization/Location/Customer/Staff/Reward/Campaign архивируются статусом.

## 47. Optimistic locking

`version BIGINT` увеличивается при изменении mutable aggregate/configuration entity.

HTTP/API command может принимать expected_version/ETag для:
- customer profile admin edit;
- loyalty tier;
- campaign;
- reward definition;
- location/category/settings;
- integrations.

Финансовые операции дополнительно используют DB transaction + row-level locks.

## 48. Row locking

При ConfirmOrder backend блокирует как минимум:
- order draft;
- points_account customer;
- выбранные customer_rewards;
- identification_session;
- customer_loyalty_state.

При RefundOrder:
- order;
- points_account;
- relevant rewards/state.

Цель — исключить двойные списания и lost updates.

## 49. Isolation

Default PostgreSQL `READ COMMITTED` допустим при корректных `SELECT ... FOR UPDATE` и constraints.

Для отдельных сложных операций можно использовать retryable `SERIALIZABLE`, но это не должно быть глобальным default без необходимости.

## 50. PII indexes

Телефон и Telegram ID индексируются для поиска. Если позже требования по privacy усиливаются, можно добавить normalized/hash search columns и field-level encryption.

Raw PII никогда не помещается в logs/outbox/audit без необходимости.

## 51. JSONB policy

JSONB используется только там, где структура действительно rule/provider-dependent:
- campaign rules/effects;
- reward config;
- integration config без секретов;
- immutable calculation snapshots;
- outbox payload.

Основные финансовые значения, статусы, FK и searchable business fields должны оставаться типизированными колонками.

## 52. Индексы для основных экранов

Минимум:
- customers(org, phone)
- customers(org, telegram_user_id)
- customers(org, status, created_at)
- orders(org, confirmed_at DESC)
- orders(customer_id, confirmed_at DESC)
- orders(staff_id, confirmed_at DESC)
- orders(location_id, confirmed_at DESC)
- points_ledger(customer_id, created_at DESC)
- customer_rewards(customer_id, status, expires_at)
- campaigns(org, status, starts_at, ends_at)
- feedback(org, status, created_at DESC)
- audit_log(org, created_at DESC)
- notifications(status, scheduled_at)
- outbox_events(published_at, available_at)

После реальных EXPLAIN ANALYZE индексы корректируются; не создавать десятки speculative indexes заранее.

## 53. Миграция V1 → V2

Рекомендуемый подход:
1. поднять V2 schema отдельно;
2. импортировать пользователей с mapping old_user_id → customer_id;
3. нормализовать Telegram ID/phone;
4. импортировать current point balance как `migration` ledger entry;
5. импортировать накопленную purchase/qualification statistic насколько V1 данные позволяют;
6. rewards/gifts преобразовать в CustomerReward;
7. orders импортировать как historical/migration orders, если данные достоверны;
8. старые неоднозначные FK Telegram/internal IDs не переносить слепо — валидировать;
9. reconciliation report: users, balances, rewards, total historical orders;
10. только после сверки переключить bots на V2 backend.

Миграция не должна пытаться воспроизвести ложную точность там, где V1 история неполная.

## 54. Alembic migration groups

Предлагаемый порядок migrations:

1. extensions + organizations + locations
2. auth/staff/roles/terminals/sessions
3. customers/profile/preferences
4. tiers + customer loyalty state/overrides/history
5. points account + ledger + lots
6. identification sessions
7. categories + orders + quotes
8. rewards
9. campaigns/segments
10. refunds
11. feedback/notifications/mailings
12. integrations/external mappings
13. audit/outbox/idempotency/settings
14. seed permissions/roles/tiers/default settings
15. V1 import tooling отдельно от schema migration

## 55. Seed data V2

Organization:
- Тейкитерия
- RUB
- Europe/Moscow

Initial tiers:
- Standard — 0 RUB — 3%
- Silver — 15 000 RUB — 5%
- Gold — 40 000 RUB — 7%
- Platinum — 80 000 RUB — 10%

Default settings:
- 30% redemption;
- 90 sec identification code;
- 10 min barista cancellation;
- 12 months inactivity period;
- cashback floor rounding;
- point expiry disabled.

## 56. Что является source of truth

- Points: `points_ledger`; `points_accounts.balance_points` — cached aggregate.
- Orders: confirmed `orders` + related calculation snapshot/ledger/reward rows.
- Rewards: `customer_rewards` + `reward_redemptions`.
- Tiers: qualification data + tier config + overrides + inactivity state; `effective_tier_id` — cached resolved state.
- Refunds: `refunds` + compensating ledger/reward/tier changes.
- Audit: `audit_log`, append-only.

## 57. Следующий технический шаг

После утверждения схемы можно создавать:
- SQLAlchemy 2.x models;
- Alembic migrations;
- repositories/unit of work;
- base FastAPI application;
- domain/application modules;
- transaction/idempotency infrastructure.

До этого момента код V1 в `main` не изменяется.
