# Модель данных V2

Это концептуальная модель. Финальные таблицы и поля фиксируются при реализации migrations.

## Customer
- id UUID/int internal;
- first_name;
- last_name optional;
- phone normalized;
- birth_date;
- status;
- created_at / updated_at.

## CustomerIdentity
Позволяет не привязывать клиента к Telegram.
- customer_id;
- provider: telegram/phone/iiko/other;
- external_id;
- verified_at;
- unique(provider, external_id).

## Staff
- id;
- name;
- status;
- created_at.

## StaffIdentity
- staff_id;
- provider;
- external_id.

## Role / Permission / StaffRole
RBAC с отдельными permissions.

## Order
- id;
- customer_id;
- staff_id nullable;
- source;
- external_order_id nullable;
- receipt_number nullable;
- gross_amount;
- discount_amount;
- points_redeemed_value;
- final_amount;
- currency;
- status;
- idempotency_key;
- confirmed_at;
- cancelled_at;
- created_at.

Уникальность `source + external_order_id` при наличии внешнего ID.

## OrderItem
- order_id;
- external_product_id nullable;
- name snapshot;
- category snapshot;
- quantity;
- unit_price;
- total_price;
- metadata JSONB для интеграционных данных, которые не являются core-полями.

## PointsAccount
- customer_id;
- cached_balance optional;
- version.

Cached balance является оптимизацией. Источник истины — ledger.

## PointsLedgerEntry
- id;
- customer_id;
- amount signed;
- operation_type;
- order_id nullable;
- campaign_id nullable;
- reason;
- created_by_staff_id nullable;
- correlation_id;
- created_at;
- reversal_of nullable.

Ledger entry после фиксации не редактируется.

## LoyaltyTier
- id;
- code stable;
- name;
- sort_order;
- qualification_type;
- qualification_config JSONB;
- benefits_config JSONB;
- active.

## CustomerTierHistory
- customer_id;
- tier_id;
- effective_from;
- effective_to;
- reason.

## RewardDefinition
Описание типа награды.
- code;
- name;
- reward_type;
- config;
- active.

## CustomerReward
Конкретно выданная награда.
- customer_id;
- reward_definition_id;
- source_type;
- source_id nullable;
- status issued/redeemed/expired/revoked;
- issued_at;
- expires_at nullable;
- redeemed_at nullable;
- redeemed_order_id nullable.

## Campaign
- code;
- name;
- status;
- starts_at / ends_at;
- audience_config;
- condition_config;
- effect_config;
- limits_config;
- priority.

JSONB здесь используется для конфигурации заранее поддерживаемых типов правил, а не для выполнения произвольного кода из БД.

## Feedback
- customer_id;
- type review/idea/contact;
- score nullable;
- text;
- status;
- assigned_staff_id nullable;
- created_at / resolved_at.

## Notification
- customer_id nullable;
- channel;
- template_code nullable;
- payload;
- status;
- attempts;
- scheduled_at;
- sent_at;
- last_error.

## AuditLog
- actor_type;
- actor_id;
- action;
- entity_type;
- entity_id;
- before JSONB nullable;
- after JSONB nullable;
- reason nullable;
- request_id;
- ip/source metadata;
- created_at.

## Integration
- id;
- type;
- name;
- status;
- non-secret config;
- created_at.

Секреты интеграций не должны возвращаться обычными API DTO и не должны попадать в audit/logs.

## ExternalMapping
Универсальный mapping внутренних сущностей к внешним системам, если специализированного identity недостаточно.

## Ключевые ограничения БД

- одноразовый код нельзя использовать дважды;
- idempotency key заказа уникален в нужной области;
- ledger immutable;
- redeemed reward нельзя использовать повторно;
- внешние идентификаторы уникальны в рамках provider;
- денежные значения хранятся integer minor units/Decimal, не float;
- timestamps — timezone-aware UTC, отображение локализует интерфейс.
