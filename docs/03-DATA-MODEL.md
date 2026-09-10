# Модель данных V2

Это концептуальная модель. Финальные таблицы и поля фиксируются при реализации migrations.

## Customer
- id internal;
- telegram_id unique, required;
- first_name;
- phone normalized;
- birth_date;
- status;
- created_at / updated_at.

Фамилия не требуется. Telegram ID определяется ботом автоматически и является обязательным пользовательским identity V2.

## Staff
- id;
- name;
- role: barista/admin;
- pin_hash;
- status;
- created_at / updated_at.

PIN не хранится в открытом виде.

## StaffTerminal
Разрешённый общий Telegram-профиль/чат рабочего устройства.
- id;
- telegram_chat_id / telegram_user_id according to selected bot model;
- name;
- active;
- created_at.

## StaffSession
Показывает, какой сотрудник сейчас работает через общий staff terminal.
- id;
- staff_id;
- terminal_id;
- started_at;
- expires_at nullable;
- ended_at nullable;
- status.

Все staff-операции должны ссылаться на Staff/StaffSession, а не на Telegram ID общего телефона.

## Role / Permission
В первой версии бизнес-роли `barista` и `admin`, но backend использует granular permissions, чтобы позже можно было без переделки добавить новые роли.

## Location
Закладывается для будущей многоточечности и большой Cafe Management Platform.
- id;
- name;
- status;
- timezone;
- created_at.

Первая версия может иметь одну location.

## IdentificationSession
Краткоживущая сессия идентификации клиента на кассе.
- id;
- customer_id;
- method: short_code / future_qr / other;
- code_hash_or_lookup_value;
- status active/used/expired/revoked;
- created_at;
- expires_at;
- used_at nullable.

Короткий код не является customer_id.

## Order
- id;
- customer_id;
- staff_id nullable;
- staff_session_id nullable;
- location_id nullable in initial version but model-ready;
- source: manual/iiko/other;
- external_order_id nullable;
- receipt_number nullable;
- gross_amount;
- points_redeemed_value;
- final_amount;
- currency;
- status;
- idempotency_key;
- confirmed_at;
- cancelled_at;
- created_at.

Уникальность `source + external_order_id` при наличии внешнего ID.

## OrderCategoryMetric
Первая версия не требует каталога товаров. Для заказа достаточно агрегированных категорий.
- order_id;
- category_code, например drinks/sandwiches;
- quantity;

Архитектура должна позволять позже заменить/дополнить это полноценными OrderItem из общей системы управления кафе.

## PointsAccount
- customer_id;
- cached_balance optional;
- version.

Cached balance — только оптимизация. Источник истины — ledger.

## PointsLedgerEntry
- id;
- customer_id;
- amount signed;
- operation_type: cashback/redeem/admin_adjustment/campaign/expiration/reversal/etc;
- order_id nullable;
- campaign_id nullable;
- reward_id nullable;
- reason nullable;
- created_by_staff_id nullable;
- correlation_id;
- created_at;
- expires_at nullable для будущего механизма сгорания;
- reversal_of nullable.

Ledger entry после фиксации не редактируется и не удаляется.

## LoyaltyTier
- id;
- code stable;
- name;
- sort_order;
- minimum_lifetime_spend;
- cashback_percent;
- active;
- created_at / updated_at.

Уровни редактируются администратором.

## CustomerLoyaltyState
Операционное состояние квалификации клиента.
- customer_id;
- automatic_tier_id;
- qualification_spend;
- last_purchase_at;
- last_inactivity_downgrade_at nullable;
- updated_at.

`qualification_spend` должен обновляться из подтверждённых/отменённых заказов по определённым правилам, а не редактироваться вручную без audit.

## CustomerTierOverride
Ручное назначение уровня администратором.
- id;
- customer_id;
- tier_id;
- valid_from;
- valid_until nullable;
- reason;
- created_by_staff_id;
- created_at;
- revoked_at nullable.

Если override активен, он имеет приоритет над automatic tier. После его окончания используется автоматический tier.

## CustomerRedemptionOverride
Временный индивидуальный лимит оплаты баллами.
- id;
- customer_id;
- max_percent, до 100;
- valid_from;
- valid_until required;
- reason nullable;
- created_by_staff_id;
- created_at;
- revoked_at nullable.

Обычный системный лимит V2 — 30%.

## CustomerTierHistory
- customer_id;
- tier_id;
- effective_from;
- effective_to;
- reason: qualification/manual_override/inactivity/override_expired/etc;
- source_staff_id nullable.

## RewardDefinition
Описание универсального типа награды.
- id;
- code;
- name;
- reward_type;
- config JSONB;
- active.

## CustomerReward
Конкретно выданная награда.
- id;
- customer_id;
- reward_definition_id;
- source_type: birthday/campaign/manual/compensation/etc;
- source_id nullable;
- status issued/redeemed/expired/revoked;
- issued_at;
- expires_at nullable;
- redeemed_at nullable;
- redeemed_order_id nullable.

Бариста может только применить уже существующую доступную награду. Создание/ручная выдача награды — административная операция.

## Campaign
- id;
- code;
- name;
- campaign_type;
- status;
- starts_at / ends_at;
- audience_config;
- condition_config;
- effect_config;
- limits_config;
- priority;
- created_at / updated_at.

JSONB используется для конфигурации заранее зарегистрированных типов правил, а не для выполнения произвольного кода из БД.

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
- status queued/sent/failed;
- attempts;
- scheduled_at;
- sent_at;
- last_error.

## AuditLog
- actor_type: customer/staff/system/integration;
- actor_id nullable;
- staff_session_id nullable;
- action;
- entity_type;
- entity_id;
- before JSONB nullable;
- after JSONB nullable;
- reason nullable;
- request_id;
- source/ip metadata;
- created_at.

Ручные изменения баллов обязательно содержат reason.

## Integration
- id;
- type/provider;
- name;
- status;
- location_id nullable;
- non-secret config;
- created_at.

Секреты интеграций не должны возвращаться обычными API DTO и не должны попадать в audit/logs.

## ExternalMapping
Mapping внутренних сущностей к внешним системам.
- integration_id;
- entity_type;
- internal_id;
- external_id;
- metadata nullable.

Это позволит подключать iiko, другую POS/ERP или будущую собственную кассовую систему без превращения внешнего ID в основной customer/staff ID.

## Системные настройки лояльности

Business settings хранятся в БД и проходят валидацию. Минимум:
- default_max_redemption_percent = 30;
- points_to_currency_rate = 1:1;
- points_expiration_enabled = false;
- tier_inactivity_period = 12 months;
- identification_code_ttl;
- barista_cancel_window = 10 minutes;
- birthday campaign settings.

Изменение настроек фиксируется в AuditLog.

## Ключевые ограничения БД

- `Customer.telegram_id` уникален;
- active identification code нельзя использовать дважды;
- idempotency key заказа уникален в нужной области;
- ledger immutable;
- redeemed reward нельзя использовать повторно;
- active staff session должна однозначно определять действующего сотрудника на terminal согласно выбранной модели сессий;
- PIN никогда не хранится plaintext;
- monetary values — Decimal или integer minor units, не float;
- проценты валидируются в допустимых пределах;
- timestamps — timezone-aware UTC, отображение локализует интерфейс;
- финансово значимые изменения выполняются транзакционно и имеют audit trail.
