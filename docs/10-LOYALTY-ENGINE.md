# Loyalty Engine V2

## 1. Назначение

Loyalty Engine — единый backend-модуль, который рассчитывает итог loyalty-операции. Telegram-боты, админка, POS-коннекторы и будущий Cafe Management Platform не рассчитывают cashback, tiers, лимиты списания, награды или акции самостоятельно.

Главный принцип: любой канал передаёт факты о заказе и выбранные действия пользователя, а backend возвращает quote/preview и затем атомарно подтверждает операцию.

## 2. Контекст расчёта

Каждый расчёт получает нормализованный контекст:
- organization_id;
- location_id;
- customer_id;
- staff_id/staff_session_id или integration principal;
- order source;
- gross amount;
- currency_code;
- category metrics / будущие line items;
- selected rewards;
- requested points redemption;
- timestamp;
- external order id/idempotency key при интеграции.

В V2 рабочая валюта RUB, но currency_code является частью модели.

## 3. Стартовые уровни

Начальная конфигурация:
- Standard: от 0 ₽, cashback 3%;
- Silver: от 15 000 ₽, cashback 5%;
- Gold: от 40 000 ₽, cashback 7%;
- Platinum: от 80 000 ₽, cashback 10%.

Это seed/config data, а не enum/константы бизнес-логики. Администратор может менять пороги и проценты.

## 4. Порядок расчёта quote

Backend обязан применять правила в детерминированном порядке.

### Шаг 1. Validation
Проверить:
- organization/location active;
- customer active и не blocked;
- staff session/permission;
- currency;
- gross amount > 0;
- категории/позиции валидны;
- identification session действительна;
- idempotency key не использован для другой команды.

### Шаг 2. Customer loyalty state
Определить:
- qualification spend;
- automatic tier;
- inactivity penalty;
- manual tier override;
- effective tier;
- active customer-specific redemption override;
- points balance;
- active rewards;
- segment membership.

### Шаг 3. Tier resolution
Базовый automatic tier определяется qualification spend.

Если действует inactivity penalty, effective automatic tier понижается на нужное число ступеней.

Если действует manual tier override, применяется его configured priority/policy.

При первой новой успешной покупке после периода неактивности inactivity penalty снимается, automatic tier пересчитывается по актуальной qualification spend, и клиент возвращается на заслуженный automatic tier, если manual override не имеет приоритета.

### Шаг 4. Campaign discovery
Найти активные кампании, подходящие по:
- organization/location scope;
- времени;
- tier;
- сегменту;
- клиенту;
- spend/order metrics;
- category metrics;
- first purchase/inactivity/birthday и другим typed conditions.

### Шаг 5. Campaign conflict resolution
Применить:
- priority;
- stackable;
- exclusivity/compatibility groups;
- explicit conflict policy.

Никакого произвольного исполняемого кода из БД.

### Шаг 6. Reward applicability
Проверить выбранные CustomerRewards:
- active;
- не истёк срок;
- quantity > 0;
- применимость к заказу/категории;
- compatibility;
- допустимость совместного использования нескольких rewards;
- допустимость одновременного использования rewards и points.

### Шаг 7. Reward/discount effects
Применить денежные эффекты rewards/campaigns до points redemption.

Получить `amount_after_rewards`.

Сумма не может стать отрицательной.

### Шаг 8. Points redemption limit
Стандартный лимит: 30% от `amount_after_rewards`.

Если есть активный CustomerRedemptionOverride, использовать его процент вплоть до 100%.

Максимум к списанию:
`min(configured_percent * amount_after_rewards, customer_points_balance, amount_after_rewards)`.

Так как 1 point = 1 RUB, monetary value points считается 1:1.

### Шаг 9. Requested redemption validation
Если клиент/бариста запросил points:
- requested_points >= 0;
- requested_points <= max_redeemable_points;
- balance достаточен.

`paid_amount = amount_after_rewards - redeemed_points_value`.

### Шаг 10. Cashback base
Если использован хотя бы 1 point:
- cashback = 0.

Если points не использованы:
- cashback base = реально оплаченная сумма после discounts/rewards;
- base cashback rate = effective tier cashback percent;
- campaign effects могут умножить или дополнить cashback согласно resolved campaign rules.

Пример: Gold 7% + x2 = 14%.

### Шаг 11. Cashback rounding
Points только целые.

Начисление округляется вниз (`floor`) до целого point.

Денежные расчёты не используют binary float; Decimal/integer minor units.

### Шаг 12. Qualification spend
Qualification spend — отдельная policy и не равна cashback base автоматически.

Базовое правило V2: в qualification идёт полная стоимость подтверждённого заказа до оплаты points. Использование points не уменьшает qualification amount.

Пример: заказ 1000 ₽, 300 ₽ оплачено points → qualification +1000 ₽.

Refund уменьшает qualification spend на возвращаемую часть.

### Шаг 13. Tier-after-order preview
После добавления qualification amount рассчитать потенциальный automatic tier после заказа.

Quote возвращает клиенту/кассиру, если покупка переводит клиента на новый tier.

## 5. Quote response

Quote должен содержать не только цифры, но и explainability:
- gross_amount;
- reward/discount effects;
- amount_after_rewards;
- points_balance;
- max_redeemable_points;
- requested/redeemed points;
- paid_amount;
- effective tier и cashback rate;
- applied campaigns;
- cashback base;
- points_to_earn;
- qualification amount;
- current/potential new tier;
- selected rewards;
- warnings/reasons;
- quote_id/version/expires_at.

## 6. Confirm order

ConfirmOrder НЕ доверяет значениям из UI quote.

В одной транзакции backend:
1. повторно валидирует actor/session/identification/idempotency;
2. блокирует/согласованно читает финансово значимое customer state;
3. перепроверяет quote/version или пересчитывает;
4. создаёт Order;
5. потребляет IdentificationSession;
6. создаёт points ledger redemption entries;
7. создаёт reward redemption entries;
8. создаёт points earning entries;
9. обновляет qualification state/read model;
10. пересчитывает automatic/effective tier;
11. пишет tier history;
12. создаёт audit/domain events;
13. сохраняет idempotency result;
14. commit.

При любой ошибке вся транзакция откатывается.

## 7. Idempotency

Любая финансово значимая команда имеет idempotency key.

Повтор той же команды:
- не создаёт вторую операцию;
- возвращает исходный результат.

Тот же idempotency key с иным payload отклоняется.

Это обязательно для Telegram double-tap, сетевых retries и POS webhooks.

## 8. Points ledger

Points balance не является единственным источником истины.

Каждое изменение — immutable ledger entry.

Типы как минимум:
- earn;
- redeem;
- refund_restore;
- earn_reversal;
- manual_credit;
- manual_debit;
- campaign_credit;
- reward_conversion;
- migration_opening_balance;
- future_expiry;
- future_expiry_reversal.

Можно хранить cached balance/read model для скорости, но он должен быть восстановим из ledger.

## 9. V1 migration

Если V1 содержит реальные balances, они импортируются как `migration_opening_balance` с source reference и timestamp миграции.

Нельзя создавать вымышленную детальную историю, которой в V1 достоверно нет.

Customer identity и проверяемые профильные данные импортируются отдельно.

Если перед запуском выяснится, что V1 данные не нужны/недостоверны, V2 может стартовать без выполнения импорта.

## 10. Refund engine

V2 поддерживает full и partial refund.

Refund — отдельная сущность/команда; исходный Order и ledger entries не удаляются.

Backend определяет refundable remainder и не допускает суммарный refund выше исходного допустимого объёма.

Refund создаёт compensating entries для:
- возвращаемых redeemed points;
- сторнирования earned points;
- qualification spend;
- rewards;
- tier state;
- campaign effects, если требуется.

При line-item POS integration refund может работать по позициям; при manual V2 допустим детерминированный proportional calculation для денежной части.

Все rounding rules фиксированы и воспроизводимы.

## 11. Birthday invariants

Birthday reward имеет yearly issuance identity/key.

Один и тот же клиент не получает второй birthday reward в том же birthday cycle, даже если:
- изменил дату рождения;
- уже использовал reward;
- reward истёк;
- администратор исправил профиль.

Клиент может изменить birth date самостоятельно только один раз; UI заранее сообщает ограничение и правило повторной выдачи.

## 12. Inactivity

Default inactivity period = 12 месяцев.

Каждый завершённый период без покупок понижает effective automatic tier на одну ступень до минимального.

При первой новой успешной покупке penalty снимается и automatic tier пересчитывается по qualification spend.

Все понижения/восстановления записываются в TierHistory.

## 13. Organization / multi-location

Organization существует с V2 как верхняя граница данных.

Сейчас одна Organization, но архитектура допускает несколько брендов/юрлиц позже.

Loyalty balance/tier/rewards общие по Organization, а Orders/Staff/Terminals/analytics имеют Location context.

Кампании V2 могут быть network-wide; data model уже допускает location scope для будущего.

## 14. Currency

RUB — единственная рабочая валюта V2.

При этом денежные сущности хранят `currency_code`, чтобы не строить доменные правила на предположении «рубль навсегда».

Cross-currency loyalty в V2 не реализуется.

## 15. Feedback notifications

Отзывы 1–5 звёзд.

По умолчанию 1–3 направляются администраторам как внутренний feedback; 4–5 могут предлагать внешний публичный отзыв.

Recipients/policy configurable: позже можно направлять manager/quality group без изменения feedback domain.

## 16. Approval workflow

V2 не требует второго администратора для ручной корректировки/refund.

Но command model допускает состояния pending_approval/approved/rejected и configurable thresholds, чтобы позже включить dual approval для крупных операций без изменения financial core.

## 17. Security / concurrency invariants

Обязательные инварианты:
- points balance не уходит ниже разрешённого значения;
- один identification session нельзя окончательно использовать дважды;
- один reward quantity нельзя redeem дважды;
- один order нельзя подтвердить дважды;
- refunds не превышают refundable remainder;
- financial writes атомарны;
- permissions проверяются backend;
- user-provided amounts никогда не считаются backend-calculated truth;
- concurrent requests используют DB locking/atomic constraints/version checks там, где существует race condition.

## 18. Extension points

Loyalty Engine расширяется через typed policies/handlers:
- EarningPolicy;
- RedemptionPolicy;
- TierPolicy;
- RewardEffectHandler;
- CampaignConditionHandler;
- CampaignEffectHandler;
- RefundPolicy;
- QualificationPolicy;
- IdentificationProvider;
- OrderProvider;
- AuthProvider.

Новая POS, новый способ auth, QR/NFC или новый тип кампании не должны требовать переписывания существующего core.

## 19. Следующий технический этап

После этого документа можно проектировать окончательные:
- application commands/queries;
- REST/API contracts;
- DB schema/migrations;
- module/package structure;
- test matrix;
- migration plan;
- implementation sequence.
