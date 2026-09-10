# Backend API & Application Contracts V2

## 1. Назначение

Этот документ определяет внешние и application-level контракты V2. Цель — отделить интерфейсы (Telegram client bot, staff bot, admin web, future Mini Apps, POS adapters) от бизнес-логики loyalty-core.

Принципы:
- Backend — единственный source of truth;
- UI/боты не вычисляют cashback, лимиты, tier, reward eligibility;
- публичные transport DTO не равны напрямую ORM-моделям;
- команды и запросы разделяются;
- финансово значимые команды идемпотентны;
- actor/permissions берутся из authenticated Principal, а не доверяются из body;
- organization/location scope выводится из Principal или явно проверенного context;
- Telegram ID, staff_id, customer_id, order_id — разные идентификаторы и никогда не подменяют друг друга;
- ошибки имеют стабильный machine code и безопасный message;
- API versioning обязателен.

Базовый REST namespace:

```text
/api/v2
```

Внутренние application commands могут не повторять REST-структуру один в один.

---

## 2. Идентификаторы

Рекомендуется использовать UUID/ULID-like opaque IDs для внутренних сущностей.

Примеры:
- organization_id
- location_id
- customer_id
- staff_id
- staff_session_id
- terminal_id
- order_id
- order_draft_id
- quote_id
- refund_id
- reward_definition_id
- customer_reward_id
- campaign_id
- identification_session_id
- ledger_entry_id

Telegram ID хранится как external identity:

```text
AuthIdentity(provider="telegram", external_subject="123456789")
```

Нельзя использовать Telegram ID вместо customer_id/staff_id в domain contracts.

---

## 3. Общий response envelope

Для REST рекомендуется единый формат.

Успех:

```json
{
  "data": {},
  "meta": {
    "request_id": "req_..."
  }
}
```

Ошибка:

```json
{
  "error": {
    "code": "INSUFFICIENT_POINTS",
    "message": "Недостаточно баллов",
    "details": {},
    "request_id": "req_..."
  }
}
```

`details` не должен содержать secrets, stack traces, SQL, PIN hash или внутренние исключения.

---

## 4. Idempotency

Обязательна для:
- ConfirmOrder;
- RefundOrder;
- AdjustPoints;
- IssueReward;
- RevokeReward;
- POS inbound financial commands;
- массовых/автоматических issuance jobs, где возможен повтор.

HTTP header:

```text
Idempotency-Key: <opaque client generated key>
```

Backend хранит ключ в scope минимум:

```text
organization + command type + actor/source + idempotency key
```

Повтор с тем же ключом и тем же payload возвращает прежний результат.
Повтор с тем же ключом, но другим payload → `IDEMPOTENCY_CONFLICT`.

---

# CLIENT API

## 5. Customer authentication

V2 provider: Telegram.

Application abstraction:

```text
AuthenticateExternalIdentity(provider, signed_payload)
  -> Principal(type=customer/admin/...)
```

Telegram-specific verification находится в TelegramAuthProvider.

Клиентские endpoints никогда не принимают `customer_id` как способ доказать личность пользователя. Customer определяется из authenticated Principal.

---

## 6. GetCustomerHome

```text
GET /api/v2/customer/home
```

Ответ:

```json
{
  "customer": {
    "id": "cus_...",
    "first_name": "Али",
    "status": "active"
  },
  "loyalty": {
    "points_balance": 1240,
    "tier": {
      "id": "tier_gold",
      "name": "Gold",
      "cashback_percent": "7.00"
    },
    "next_tier": {
      "name": "Platinum",
      "remaining_spend_minor": 2350000,
      "currency_code": "RUB"
    }
  },
  "rewards": {
    "available_count": 2
  },
  "active_campaigns_count": 1
}
```

UI получает готовое customer-facing состояние.

---

## 7. RegisterCustomer

```text
POST /api/v2/customer/registration
```

Body:

```json
{
  "first_name": "Али",
  "phone_contact_token": "verified-telegram-contact-reference",
  "birth_date": "1995-05-21"
}
```

Важно: raw arbitrary phone string не считается подтверждённым номером, если policy требует Telegram contact share.

Результат:

```json
{
  "customer_id": "cus_...",
  "status": "active"
}
```

Ошибки:
- `CUSTOMER_ALREADY_REGISTERED`
- `PHONE_NOT_VERIFIED`
- `BIRTH_DATE_INVALID`
- `REGISTRATION_NOT_ALLOWED`

---

## 8. ChangeCustomerPhone

```text
POST /api/v2/customer/profile/change-phone
```

Body:

```json
{
  "phone_contact_token": "verified-new-contact"
}
```

Backend валидирует принадлежность контакта текущему Telegram user согласно Telegram provider policy.

---

## 9. ChangeBirthDate

```text
POST /api/v2/customer/profile/change-birth-date/preview
POST /api/v2/customer/profile/change-birth-date/confirm
```

Preview возвращает предупреждение:
- дата рождения может быть изменена клиентом только один раз;
- уже выданный/использованный birthday reward в текущем году повторно не выдаётся.

Confirm body:

```json
{
  "new_birth_date": "1995-05-22",
  "confirmation_token": "birth_change_preview_token"
}
```

Ошибки:
- `BIRTH_DATE_CHANGE_LIMIT_REACHED`
- `BIRTH_DATE_INVALID`
- `PREVIEW_EXPIRED`

---

## 10. GenerateIdentificationCode

```text
POST /api/v2/customer/identification/code
```

Application command:

```text
GenerateIdentificationCode(customer_principal)
```

Ответ:

```json
{
  "identification_session_id": "ids_...",
  "code": "58321",
  "expires_at": "2026-09-10T14:31:30+03:00",
  "ttl_seconds": 90
}
```

Правила:
- code = ровно 5 цифр;
- TTL default = 90 sec;
- один активный identification session на customer/provider policy;
- генерация нового кода может invalidate предыдущий;
- code не является customer_id;
- lookup кода не consumе его;
- consume происходит только в успешном ConfirmOrder transaction.

Ошибки:
- `CUSTOMER_BLOCKED`
- `IDENTIFICATION_RATE_LIMITED`

---

## 11. GetCustomerRewards

```text
GET /api/v2/customer/rewards?status=available
```

Ответ содержит только customer-facing reward данные:

```json
{
  "items": [
    {
      "id": "crw_...",
      "name": "Бесплатный напиток",
      "description": "Любой напиток из разрешённой категории",
      "quantity_available": 2,
      "valid_until": "2026-09-17T23:59:59+03:00",
      "source_label": "Подарок на день рождения"
    }
  ]
}
```

---

## 12. GetCustomerHistory

```text
GET /api/v2/customer/history?cursor=...
```

Unified timeline read model может включать:
- order;
- points earned/redeemed/refunded;
- reward issued/redeemed;
- tier change.

Transport не обязан выдавать сырые ledger rows.

---

## 13. SubmitFeedback

```text
POST /api/v2/customer/feedback
```

Body:

```json
{
  "rating": 5,
  "text": "...",
  "order_id": "ord_..."
}
```

Rating: integer 1..5.

Ответ может вернуть action recommendation:

```json
{
  "feedback_id": "fb_...",
  "next_action": {
    "type": "external_review_offer",
    "url": "https://..."
  }
}
```

Для низкой оценки backend создаёт internal notification согласно configurable routing.

---

# STAFF AUTH & SESSION API

## 14. ResolveStaffTerminal

Staff Telegram bot после webhook/update не передаёт trusted terminal_id напрямую из клиента.

Application layer получает verified Telegram identity и выполняет:

```text
ResolveStaffTerminal(external_identity)
```

Ответ:

```json
{
  "terminal_id": "term_...",
  "location_id": "loc_...",
  "active_staff_session": null
}
```

Если identity не разрешён → `STAFF_TERMINAL_NOT_ALLOWED`.

---

## 15. StaffLoginWithPin

```text
POST /api/v2/staff/session/login
```

Body:

```json
{
  "pin": "123456"
}
```

Terminal берётся из authenticated Telegram terminal Principal/context.

Backend:
- принимает только 6 digits;
- проверяет hash;
- PIN уникален в Organization;
- Staff active;
- Staff.location_id совпадает с Terminal.location_id;
- 5 ошибок → 5 min lockout;
- последующие серии увеличивают lockout;
- audit successful/failed attempt.

Ответ:

```json
{
  "staff_session_id": "ssn_...",
  "staff": {
    "id": "stf_...",
    "name": "Магомед",
    "role": "barista"
  },
  "location": {
    "id": "loc_...",
    "name": "Тейкитерия"
  }
}
```

Ошибки намеренно не раскрывают наличие конкретного PIN:
- `INVALID_STAFF_CREDENTIALS`
- `STAFF_LOGIN_LOCKED`

---

## 16. StaffLogout

```text
POST /api/v2/staff/session/logout
```

Закрывает текущую staff session.

Admin отдельно может revoke session.

---

# ORDER APPLICATION CONTRACTS

## 17. CreateOrderDraft

```text
POST /api/v2/staff/orders/drafts
```

Command:

```text
CreateOrderDraft(
  principal,
  staff_session_id
)
```

Backend сам фиксирует:
- organization_id;
- location_id;
- staff_id;
- source = manual;
- created_at.

Ответ:

```json
{
  "order_draft_id": "odr_...",
  "status": "draft",
  "expires_at": "..."
}
```

---

## 18. IdentifyCustomerForDraft

```text
POST /api/v2/staff/orders/drafts/{draft_id}/identify
```

Body:

```json
{
  "code": "58321"
}
```

Backend resolve identification session и связывает customer с draft, но session пока не consume.

Ответ:

```json
{
  "customer": {
    "display_name": "Али",
    "tier_name": "Gold",
    "points_balance": 1240,
    "available_rewards_count": 2
  },
  "identification_session_expires_at": "..."
}
```

PII минимизированы.

Ошибки:
- `IDENTIFICATION_INVALID`
- `IDENTIFICATION_EXPIRED`
- `IDENTIFICATION_ALREADY_USED`
- `CUSTOMER_BLOCKED`

---

## 19. UpdateManualOrderInput

```text
PUT /api/v2/staff/orders/drafts/{draft_id}/input
```

Body:

```json
{
  "gross_amount_minor": 100000,
  "currency_code": "RUB",
  "category_metrics": [
    {"category_id": "cat_drink", "quantity": 2},
    {"category_id": "cat_sandwich", "quantity": 1}
  ]
}
```

Money передаётся в minor units. Для RUB 100000 = 1000.00 ₽.

Backend валидирует currency организации/location и categories.

---

## 20. QuoteOrder

```text
POST /api/v2/staff/orders/drafts/{draft_id}/quote
```

Body может содержать пользовательский выбор:

```json
{
  "requested_points_to_redeem": 200,
  "requested_rewards": [
    {"customer_reward_id": "crw_...", "quantity": 1}
  ]
}
```

Backend рассчитывает всё заново.

Ответ:

```json
{
  "quote_id": "quo_...",
  "quote_version": 4,
  "expires_at": "...",
  "order": {
    "gross_amount_minor": 100000,
    "currency_code": "RUB",
    "reward_discount_minor": 0,
    "discounted_amount_before_points_minor": 100000,
    "points_balance": 1240,
    "redemption_limit_percent": "30.00",
    "max_points_redeemable": 300,
    "points_to_redeem": 200,
    "cash_paid_amount_minor": 80000,
    "cashback_base_minor": 80000,
    "points_to_earn": 0,
    "qualification_amount_minor": 100000
  },
  "tier": {
    "name": "Gold",
    "base_cashback_percent": "7.00"
  },
  "campaigns": [],
  "rewards": [],
  "explanations": [
    {
      "code": "NO_CASHBACK_WHEN_POINTS_USED",
      "text": "Cashback не начисляется, потому что в заказе используются баллы"
    }
  ]
}
```

Quote — не финансовая операция.

---

## 21. Calculate max redemption

Backend policy:

```text
base_after_rewards_and_discounts
× applicable_redemption_limit_percent
= monetary maximum
```

Затем ограничение:

```text
min(monetary maximum converted to points, current points balance)
```

Default limit = 30%.
Customer override может временно поднять до 100%.

---

## 22. Cashback calculation

Если `points_to_redeem > 0`:

```text
points_to_earn = 0
```

Иначе:

```text
cashback_base = actually_paid_amount_after_rewards_and_discounts
cashback_rate = tier rate modified by applicable campaigns
raw_points = cashback_base × cashback_rate
points_to_earn = floor(raw_points in points)
```

Все вычисления Decimal/integer-safe, не binary float.

---

## 23. ConfirmOrder

```text
POST /api/v2/staff/orders/drafts/{draft_id}/confirm
Idempotency-Key: ...
```

Body:

```json
{
  "quote_id": "quo_...",
  "quote_version": 4
}
```

Не передавать повторно trusted `points_to_earn`, `max_redeem`, `tier`, `staff_id`, `customer_id`.

Backend transaction:
1. validates principal/staff session;
2. locks/revalidates draft/customer/points/rewards/identification;
3. revalidates quote/version/policies;
4. reserves/consumes rewards;
5. consumes identification session;
6. creates Order;
7. writes points ledger entries;
8. updates cached points balance safely;
9. updates qualification spend;
10. recalculates automatic/effective tier;
11. writes tier history if changed;
12. records campaign applications;
13. creates audit/domain events/outbox;
14. commits atomically.

Ответ:

```json
{
  "order_id": "ord_...",
  "order_number": "A1042",
  "status": "confirmed",
  "gross_amount_minor": 100000,
  "currency_code": "RUB",
  "points_redeemed": 200,
  "points_earned": 0,
  "customer_points_balance": 1040,
  "effective_tier": "Gold",
  "customer_notification_scheduled": true
}
```

Ошибки:
- `QUOTE_STALE`
- `IDENTIFICATION_EXPIRED`
- `INSUFFICIENT_POINTS`
- `REWARD_UNAVAILABLE`
- `STAFF_SESSION_ENDED`
- `ORDER_ALREADY_CONFIRMED`
- `CUSTOMER_BLOCKED`

---

## 24. GetOrderByIdempotencyKey

При сетевой неопределённости staff bot должен уметь выяснить результат:

```text
GET /api/v2/staff/orders/idempotency/{key}
```

или внутренний query `ResolveCommandResult`.

Нельзя автоматически создавать новый заказ после timeout подтверждения.

---

## 25. GetMyRecentOrders

```text
GET /api/v2/staff/orders/mine?limit=20
```

Фильтруется backend по authenticated Staff.

Response field:

```json
{
  "items": [
    {
      "order_id": "ord_...",
      "order_number": "A1042",
      "created_at": "...",
      "gross_amount_minor": 100000,
      "status": "confirmed",
      "can_barista_cancel": true,
      "barista_cancel_until": "..."
    }
  ]
}
```

---

## 26. CancelOwnOrder

Для ошибочной barista cancellation <= 10 min:

```text
POST /api/v2/staff/orders/{order_id}/cancel
Idempotency-Key: ...
```

Body:

```json
{
  "reason": "Ошибочно проведена операция"
}
```

Backend проверяет ownership, permission, 10-minute window и status.

Создаёт compensating records, а не удаляет Order.

---

# REFUND CONTRACTS

## 27. PreviewRefund

Admin/POS flow:

```text
POST /api/v2/admin/orders/{order_id}/refunds/preview
```

Body full refund:

```json
{
  "type": "full"
}
```

Partial:

```json
{
  "type": "partial",
  "refund_amount_minor": 35000,
  "category_metrics": []
}
```

Когда POS item-level data доступна, adapter может передавать normalized line references.

Ответ объясняет последствия:

```json
{
  "refund_preview_id": "rfp_...",
  "money_refund_minor": 35000,
  "points_to_restore": 70,
  "earned_points_to_reverse": 24,
  "qualification_spend_to_reverse_minor": 35000,
  "rewards": [],
  "tier_after_refund": "Silver"
}
```

---

## 28. ConfirmRefund

```text
POST /api/v2/admin/orders/{order_id}/refunds
Idempotency-Key: ...
```

Body:

```json
{
  "refund_preview_id": "rfp_...",
  "reason": "Возврат гостю"
}
```

Backend повторно валидирует refundable remainder.

Refund immutable, исходный Order не переписывается как будто операции не было.

---

# ADMIN CUSTOMER COMMANDS

## 29. BlockCustomer

```text
POST /api/v2/admin/customers/{customer_id}/block
```

Body:

```json
{
  "reason": "..."
}
```

Permission `customers.block`.
Audit mandatory.

Unblock — отдельная команда.

---

## 30. AdjustPoints

```text
POST /api/v2/admin/customers/{customer_id}/points/adjustments
Idempotency-Key: ...
```

Body:

```json
{
  "delta_points": 500,
  "reason": "Компенсация клиенту"
}
```

Negative delta допускается только при достаточном balance согласно policy.

Никакого прямого `set balance = X`.

---

## 31. SetTierOverride

```text
POST /api/v2/admin/customers/{customer_id}/tier-override
```

Body:

```json
{
  "tier_id": "tier_gold",
  "starts_at": "2026-09-10T00:00:00+03:00",
  "ends_at": null,
  "reason": "VIP"
}
```

Backend продолжает вести automatic tier state параллельно.

Policy поведения после окончания override конфигурируема.

---

## 32. SetRedemptionOverride

```text
POST /api/v2/admin/customers/{customer_id}/redemption-override
```

Body:

```json
{
  "limit_percent": "100.00",
  "ends_at": "2026-09-17T23:59:59+03:00",
  "reason": "Компенсация"
}
```

`ends_at` обязателен.

---

# REWARDS

## 33. CreateRewardDefinition

```text
POST /api/v2/admin/reward-definitions
```

Typed config, например:

```json
{
  "name": "Бесплатный напиток",
  "type": "category_free_item",
  "config": {
    "category_ids": ["cat_drink"],
    "max_unit_value_minor": null
  },
  "default_validity_days": 30,
  "stackable": true,
  "active": true
}
```

Backend schema-validates config по handler type.

Нельзя хранить произвольный executable code.

---

## 34. IssueReward

```text
POST /api/v2/admin/customers/{customer_id}/rewards
Idempotency-Key: ...
```

Body:

```json
{
  "reward_definition_id": "rwd_...",
  "quantity": 1,
  "valid_until": "...",
  "reason": "Компенсация"
}
```

---

## 35. RevokeReward

```text
POST /api/v2/admin/customer-rewards/{customer_reward_id}/revoke
```

Reason mandatory.

---

# TIERS

## 36. Tier CRUD

```text
GET    /api/v2/admin/tiers
POST   /api/v2/admin/tiers
PATCH  /api/v2/admin/tiers/{tier_id}
```

Deletion активного/использованного tier лучше заменить deactivate/archive.

Initial defaults:
- Standard: threshold 0 ₽, 3%
- Silver: threshold 15,000 ₽, 5%
- Gold: threshold 40,000 ₽, 7%
- Platinum: threshold 80,000 ₽, 10%

Все значения admin-configurable и не hardcoded domain enum.

До save backend validates monotonic thresholds/order.

---

## 37. Tier impact preview

Перед крупным изменением thresholds:

```text
POST /api/v2/admin/tiers/impact-preview
```

Возвращает approximate/exact number клиентов, которые изменят automatic tier.

---

# CAMPAIGNS

## 38. Campaign model contract

Пример normalized campaign DTO:

```json
{
  "name": "Двойной кешбэк вечером",
  "status": "draft",
  "priority": 100,
  "stacking": {
    "stackable": true,
    "exclusive_group": null
  },
  "scope": {
    "organization_id": "org_...",
    "location_ids": []
  },
  "schedule": {
    "starts_at": "...",
    "ends_at": "...",
    "days_of_week": [5, 6],
    "time_from": "18:00",
    "time_to": "23:00"
  },
  "conditions": [
    {"type": "tier_in", "tier_ids": ["tier_gold", "tier_platinum"]}
  ],
  "effects": [
    {"type": "cashback_multiplier", "multiplier": "2.00"}
  ]
}
```

Conditions/effects schema-versioned and typed.

---

## 39. TestCampaign

```text
POST /api/v2/admin/campaigns/test
```

Admin может выбрать customer/order context и получить explainable result без создания финансовой операции.

---

## 40. Campaign lifecycle

Commands:
- create draft;
- validate;
- schedule/publish;
- pause;
- resume;
- finish/archive.

Изменение активной кампании, влияющее на расчёты, создаёт новую config version/effective version вместо бесследного переписывания истории.

Orders сохраняют applied campaign version references.

---

# STAFF / TERMINALS / LOCATIONS

## 41. CreateStaff

```text
POST /api/v2/admin/staff
```

Body:

```json
{
  "name": "Магомед",
  "role": "barista",
  "location_id": "loc_...",
  "pin": "123456"
}
```

Backend hash PIN immediately. Raw PIN не логируется и не возвращается.

---

## 42. ResetStaffPin

```text
POST /api/v2/admin/staff/{staff_id}/reset-pin
```

Body contains new 6-digit PIN. Unique across organization.

Может revoke active staff sessions по policy.

---

## 43. RegisterStaffTerminal

```text
POST /api/v2/admin/staff-terminals
```

Body использует verified Telegram identity/reference, а не произвольный chat id без подтверждения.

Terminal привязывается к одной Location.

---

## 44. Locations

```text
GET/POST/PATCH /api/v2/admin/locations
```

Location содержит organization_id implicitly scoped backendом.

---

# CATEGORIES

## 45. Order categories

```text
GET  /api/v2/staff/order-categories
GET  /api/v2/admin/order-categories
POST /api/v2/admin/order-categories
PATCH /api/v2/admin/order-categories/{category_id}
```

Category DTO:

```json
{
  "id": "cat_drink",
  "code": "drink",
  "display_name": "Напитки",
  "active": true,
  "sort_order": 10
}
```

Категории — data-driven.

---

# SEGMENTS & MAILINGS

## 46. Segments

Динамический Segment:

```json
{
  "name": "Не были 60 дней",
  "type": "dynamic",
  "rules": [
    {"type": "days_since_last_purchase_gte", "value": 60}
  ]
}
```

Rules typed/schema-versioned.

---

## 47. CreateMailing

```text
POST /api/v2/admin/mailings
```

Fields:
- audience segment;
- content;
- buttons/deep link;
- scheduled_at;
- marketing vs transactional classification;
- test recipients.

Send worker читает immutable mailing version and snapshots/resolves audience according to defined policy.

---

# FEEDBACK

## 48. Admin feedback API

```text
GET /api/v2/admin/feedback
GET /api/v2/admin/feedback/{id}
POST /api/v2/admin/feedback/{id}/resolve
```

Internal routing recipients are configurable by permission group/notification rule, not hardcoded Telegram IDs.

---

# ANALYTICS

## 49. Analytics queries

Read-only endpoints должны быть отдельными query handlers.

Examples:

```text
GET /api/v2/admin/analytics/overview
GET /api/v2/admin/analytics/points
GET /api/v2/admin/analytics/tiers
GET /api/v2/admin/analytics/campaigns/{id}
```

Filters:
- date_from/date_to;
- location_id;
- tier_id;
- segment_id;
- campaign_id.

Не смешивать аналитические queries с transactional commands.

---

# INTEGRATIONS

## 50. POS provider contract

Conceptual port:

```text
OrderSourceProvider
- normalize_order(external_payload) -> NormalizedOrderInput
- normalize_refund(external_payload) -> NormalizedRefundInput
- acknowledge(result)
```

Loyalty core работает с normalized DTO.

Providers:
- ManualOrderProvider
- IikoOrderProvider
- RKeeperOrderProvider
- CustomPOSProvider
- InternalCafeOrderProvider

---

## 51. Inbound POS order

Пример:

```text
POST /api/v2/integrations/{connection_id}/orders
```

Security зависит от provider: signed webhook/API credential/mTLS later.

Required:
- external_order_id;
- external idempotency/event id;
- location mapping;
- amount/currency;
- normalized items/category metrics;
- operation timestamp.

Connection определяет organization и allowed locations; body не может самовольно переключить tenant.

---

## 52. External mappings

Universal mapping table/API для:
- locations;
- order categories;
- products later;
- staff where needed;
- customer external IDs where legally/technically appropriate.

Core не хранит iiko-specific columns в Order/Customer.

---

# ORGANIZATION & TENANCY

## 53. Organization boundary

Даже при одной Тейкитерии V2 имеет Organization как верхний ownership/security boundary.

Все tenant-owned entities содержат organization ownership напрямую или однозначно через aggregate/root.

Каждый query/command обязательно scoped к Principal.organization_id.

Нельзя принимать organization_id из frontend и просто доверять ему.

Это позволяет будущей Cafe Management Platform поддерживать несколько брендов/организаций без переделки фундаментальной модели.

---

# AUTHORIZATION

## 54. Principal

Пример internal principal:

```text
Principal
- principal_id
- type: customer | staff | admin | integration | system
- organization_id
- auth_session_id
- permissions[]
- external_identity_ref
```

Customer permissions не являются staff RBAC role.

---

## 55. Permission checks

Application handler сам проверяет нужную capability.

Пример:

```text
AdjustPointsHandler requires points.adjust
RefundOrderHandler requires orders.refund
CreateCampaignHandler requires campaigns.manage
```

UI hidden button ≠ security.

---

# CONCURRENCY & TRANSACTIONS

## 56. Points concurrency

На ConfirmOrder/Refund/AdjustPoints backend должен защищать customer PointsAccount от lost update.

Допустимые механизмы:
- row-level lock;
- optimistic version + retry;
- atomic guarded updates.

Immutable ledger + balance cache должны изменяться одной transaction.

---

## 57. Reward concurrency

CustomerReward redemption должен быть атомарным и проверять remaining quantity в DB transaction.

Нельзя полагаться на количество, показанное несколько секунд назад в Telegram.

---

## 58. Quote concurrency

Quote — snapshot calculation. Confirm не обязан слепо доверять quote.

Если баланс, reward, campaign version, tier config или critical state изменились → `QUOTE_STALE` и новый quote.

---

# EVENTS / OUTBOX

## 59. Domain events

Примеры:
- CustomerRegistered
- OrderConfirmed
- OrderRefunded
- PointsEarned
- PointsRedeemed
- TierChanged
- RewardIssued
- RewardRedeemed
- FeedbackSubmitted
- StaffSessionStarted

Events создаются в transaction вместе с domain change через transactional outbox.

Notification workers/analytics/integrations не должны требовать distributed transaction с Telegram.

---

# API SECURITY

## 60. Security requirements

- TLS only;
- short-lived sessions/tokens;
- secure cookies for admin web where applicable;
- CSRF protection for cookie auth;
- rate limiting;
- request size limits;
- strict DTO validation;
- secrets in secret store/env, never API response;
- PII access permissioned/audited;
- PIN hash Argon2id or equivalent modern password KDF;
- no sensitive values in logs;
- webhook signature/Telegram payload verification;
- CORS allowlist;
- security headers in admin UI;
- pagination limits;
- exports permissioned and auditable.

---

# VERSIONING

## 61. API versioning strategy

Transport major version in path: `/api/v2`.

Campaign condition/effect configs additionally имеют own `schema_version`.

External integrations may have provider adapter version independent from loyalty API version.

Breaking DTO changes require V3 or migration/compatibility period.

---

# STANDARD ERROR CODES

## 62. Core error registry

Минимальный стабильный registry:

```text
AUTH_REQUIRED
AUTH_INVALID
PERMISSION_DENIED
RESOURCE_NOT_FOUND
VALIDATION_ERROR
CONFLICT
RATE_LIMITED
IDEMPOTENCY_CONFLICT
CUSTOMER_BLOCKED
CUSTOMER_ALREADY_REGISTERED
PHONE_NOT_VERIFIED
BIRTH_DATE_CHANGE_LIMIT_REACHED
IDENTIFICATION_INVALID
IDENTIFICATION_EXPIRED
IDENTIFICATION_ALREADY_USED
IDENTIFICATION_RATE_LIMITED
STAFF_TERMINAL_NOT_ALLOWED
INVALID_STAFF_CREDENTIALS
STAFF_LOGIN_LOCKED
STAFF_SESSION_ENDED
ORDER_DRAFT_EXPIRED
ORDER_ALREADY_CONFIRMED
QUOTE_STALE
INSUFFICIENT_POINTS
REDEMPTION_LIMIT_EXCEEDED
REWARD_UNAVAILABLE
CAMPAIGN_CONFLICT
REFUND_EXCEEDS_REMAINDER
BARISTA_CANCEL_WINDOW_EXPIRED
CURRENCY_NOT_SUPPORTED
INTEGRATION_MAPPING_MISSING
EXTERNAL_EVENT_DUPLICATE
```

Bots map machine codes to localized UX text.

---

# COMMAND / QUERY CATALOG

## 63. Core application commands

Customer:
- RegisterCustomer
- ChangeCustomerPhone
- ChangeBirthDate
- GenerateIdentificationCode
- SubmitFeedback

Staff:
- StartStaffSession
- EndStaffSession
- CreateOrderDraft
- IdentifyCustomerForDraft
- UpdateOrderDraftInput
- QuoteOrder
- ConfirmOrder
- CancelOwnOrder

Admin:
- BlockCustomer / UnblockCustomer
- AdjustPoints
- Set/ClearTierOverride
- Set/ClearRedemptionOverride
- PreviewRefund / RefundOrder
- Create/UpdateRewardDefinition
- IssueReward / RevokeReward
- Create/UpdateTier
- Create/Update/Publish/PauseCampaign
- Create/UpdateSegment
- Create/Schedule/CancelMailing
- Create/DeactivateStaff / ResetStaffPin / RevokeStaffSession
- Create/UpdateLocation
- Create/RevokeStaffTerminal
- Create/UpdateOrderCategory
- ConfigureIntegration
- UpdateBusinessSettings

System:
- RunBirthdayIssuance
- RunTierInactivityEvaluation
- ExpireOverrides
- ExpireRewards
- ProcessOutbox
- ProcessMailingBatch
- ProcessIntegrationEvent

---

## 64. Core queries

Customer:
- GetCustomerHome
- GetCustomerProfile
- GetCustomerRewards
- GetCustomerHistory
- GetActiveCampaignsForCustomer

Staff:
- GetCurrentStaffSession
- GetOrderDraft
- GetMyRecentOrders
- GetMyOrder
- GetActiveOrderCategories

Admin:
- SearchCustomers
- GetCustomerDetail
- GetPointsLedger
- SearchOrders
- GetOrderDetail
- GetRefundDetail
- ListTiers
- ListRewardDefinitions
- ListCustomerRewards
- ListCampaigns
- TestCampaign
- ListSegments
- ListStaff
- ListStaffSessions
- ListStaffTerminals
- ListLocations
- ListFeedback
- Analytics queries
- AuditLog queries
- Integration status queries

---

# CONTRACT TESTING

## 65. Обязательные contract tests

Нужно тестировать не только happy path, но и invariants:
- Telegram ID никогда не трактуется как customer_id;
- duplicate ConfirmOrder с одним idempotency key создаёт один Order;
- два конкурентных списания не дают отрицательный balance;
- reward quantity нельзя потратить дважды;
- expired identification code не проходит confirm;
- lookup identification не consume code;
- points usage => cashback exactly zero;
- cashback без points считается с actual paid amount;
- redemption limit считается после rewards/discounts;
- floor rounding points;
- partial refunds суммарно не превышают refundable amount;
- refund создаёт compensating ledger;
- cross-organization access невозможен;
- barista не может отменить чужой order;
- barista cancellation >10 min отклоняется;
- financial config version сохраняется в order calculation trace;
- birthday issuance idempotent per customer/year cycle.

---

# OPENAPI

## 66. OpenAPI

FastAPI генерирует OpenAPI, но generated schema не заменяет application contracts.

Требования:
- DTO описаны явно;
- examples для critical flows;
- security schemes;
- documented machine error codes;
- no ORM serialization as implicit API;
- autogenerated client SDK later possible.

---

# IMPLEMENTATION BOUNDARY

## 67. Рекомендуемая структура backend

```text
src/
  platform/
    auth/
    organizations/
    locations/
    staff/
    customers/
    orders/

  loyalty/
    accounts/
    points/
    tiers/
    rewards/
    campaigns/
    segments/
    identification/

  communications/
    notifications/
    feedback/
    mailings/

  integrations/
    core/
    manual/
    iiko/        # later
    rkeeper/     # later

  interfaces/
    http/
    telegram_client/
    telegram_staff/
    admin_web/

  infrastructure/
    db/
    outbox/
    scheduler/
    cache/
```

Modules communicate through application interfaces/events, not by importing Telegram handlers into domain logic.

---

## 68. Definition of Done для API design

Перед началом основной реализации должно быть возможно:
1. по этому документу создать Pydantic request/response schemas;
2. построить FastAPI routes без решения новых бизнес-вопросов;
3. реализовать handlers отдельно от Telegram;
4. написать integration/contract tests;
5. позже заменить manual order source на POS adapter без изменения loyalty engine;
6. позже добавить Mini App/mobile interface без изменения доменных правил;
7. встроить loyalty module в Cafe Management Platform без смены tenant/auth foundations.
