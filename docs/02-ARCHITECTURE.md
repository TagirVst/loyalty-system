# Архитектура V2

## Подход

На старте используем **модульный монолит**, а не микросервисы. Это проще в разработке и эксплуатации, но границы модулей проектируются так, чтобы в будущем loyalty мог стать частью большой Cafe Management Platform без переписывания core.

## Предлагаемая структура

```text
backend/
  app/
    api/
      v1/
    core/
      config/
      security/
      events/
      exceptions/
    modules/
      customers/
      staff/
      locations/
      orders/
      loyalty/
      rewards/
      campaigns/
      feedback/
      notifications/
      analytics/
      audit/
      integrations/
    db/
    jobs/

interfaces/
  telegram/
    client_bot/
    staff_bot/
  admin/

tests/
  unit/
  integration/
  e2e/

docs/
```

Каждый доменный модуль разделяется минимум на domain/application/infrastructure/api по мере необходимости. Не требуется искусственно создавать одинаковое число слоёв в каждом маленьком модуле, но зависимости должны соблюдать направление внутрь домена.

## Правило зависимости

```text
Telegram / Admin / External API
            |
            v
      Backend API
            |
            v
 Application services
            |
            v
        Domain
            |
            v
 Repository interfaces
            ^
            |
 Infrastructure implementations
```

Domain не знает о Telegram, HTML, FastAPI, iiko или конкретной POS.

## Главный принцип

**Backend является единственным источником истины.**

Telegram-боты не рассчитывают cashback, уровни, лимиты списания, подарки или возвраты. Они только собирают ввод, вызывают backend и показывают результат.

То же относится к будущей POS-интеграции и админке.

## Принцип расширяемости

Ни один внешний интерфейс или конкретный провайдер не должен становиться обязательной частью domain/application слоёв.

В V2 Telegram является единственным способом входа пользователей и сотрудников, но backend не должен считать Telegram самой моделью аутентификации. Telegram — только первый `AuthProvider`.

Новые способы входа должны подключаться отдельными адаптерами без изменения customers, staff, orders, loyalty и других доменных модулей.

Концептуально:

```text
TelegramAuthProvider  ─┐
FuturePasswordAuth    ─┼─> AuthService -> Principal/Session -> Backend permissions
FutureOAuthProvider   ─┤
FutureSSOProvider     ─┘
```

Для первой версии реализуется только `TelegramAuthProvider`. Пароли, OAuth, SSO и другие способы не реализуются, пока не понадобятся.

Тот же принцип применяется к POS, уведомлениям, идентификации клиента, хранилищу файлов и другим интеграциям: сначала минимально необходимая реализация, но стабильный внутренний контракт для будущих адаптеров.

## Модули

### customers
Общий профиль клиента. В V2 основной пользовательский identity — Telegram. В будущем модуль может стать общеплатформенным.

### staff
Сотрудники, роли, permissions, PIN-аутентификация на общем staff-устройстве, staff sessions.

### locations
Точки/филиалы. Даже если первая установка работает в одном кафе, архитектура должна позволять связывать сотрудников, заказы и интеграции с location без переноса всей модели позже.

### orders
Заказ как общая бизнес-сущность, источник заказа, ручной ввод/POS, расчёт, подтверждение, отмена, идемпотентность.

### loyalty
Ledger баллов, баланс, cashback policies, лимиты списания, qualification spend, автоматические и ручные tier overrides.

### rewards
Определения наград, выданные клиенту экземпляры, сроки, использование и отмена.

### campaigns
Расширяемые правила акций, аудитории, условия и эффекты.

### feedback
Отзывы, идеи, обращения и обработка.

### notifications
Шаблоны, задания доставки, каналы и статусы.

### analytics
Read-модели/агрегации. Аналитика не должна менять доменные данные.

### audit
Кто, когда, откуда и что изменил.

### integrations
Адаптеры внешних систем, webhook endpoints, API credentials и mapping внешних ID.

## Telegram как интерфейс

### Client bot
Клиентский бот идентифицирует пользователя по Telegram ID. Telegram ID приходит от Telegram API и не вводится клиентом вручную.

### Staff bot
Staff-бот может работать на одном общем Telegram-профиле/телефоне кафе.

Рабочий сценарий:
1. администратор разрешает Telegram-профиль как staff terminal;
2. бариста вводит свой персональный 4–6-значный PIN;
3. backend создаёт staff session;
4. последующие операции привязываются к конкретному Staff;
5. logout/timeout/администратор завершает session.

PIN никогда не является идентификатором сотрудника и хранится только как hash. Авторизация и проверка permissions происходят на backend.

### Admin authentication
В V2 администратор входит только через свой разрешённый Telegram-профиль. Отдельный логин/пароль не реализуется.

При этом admin UI не должен напрямую проверять Telegram ID в бизнес-коде. Он получает подтверждённую identity/session от общего `AuthService`. Благодаря этому позже можно добавить другой способ входа без переписывания админки и доменных модулей.

## Идентификация клиента на продаже

Пятизначный временный код является отдельной `IdentificationSession`, а не ID клиента.

```text
Customer -> IdentificationSession -> Order draft
```

Это позволяет позже добавить QR/NFC/другой способ, не меняя order и loyalty services.

## Источники заказа

Первая версия:

```text
ManualOrderProvider
```

Staff вводит сумму и категорийные количества вручную.

Будущие варианты:

```text
IikoOrderProvider
RKeeperOrderProvider
CustomPOSProvider
InternalCafeOrderProvider
```

Все providers преобразуют входные данные в единый доменный `OrderInput`. Loyalty-core не знает, откуда пришёл заказ.

## События

Для слабого связывания модулей использовать domain/application events, например:
- `OrderConfirmed`;
- `OrderCancelled`;
- `PointsEarned`;
- `PointsRedeemed`;
- `TierChanged`;
- `RewardIssued`;
- `RewardRedeemed`;
- `CustomerBirthdayReached`;
- `StaffSessionStarted`;
- `StaffSessionEnded`.

На старте события могут обрабатываться внутри одного процесса. Интерфейс событий должен позволять позже подключить очередь без переписывания доменной логики.

## Расширяемость правил

Нельзя размазывать правила по роутам и ботам. Использовать стратегии/политики.

Примеры:

```python
class EarningPolicy(Protocol):
    def calculate(self, context: OrderContext) -> PointsResult: ...

class RedemptionPolicy(Protocol):
    def calculate_limit(self, context: OrderContext) -> RedemptionLimit: ...

class TierPolicy(Protocol):
    def resolve(self, context: CustomerQualificationContext) -> TierResult: ...
```

Новые политики регистрируются централизованно. Настройки конкретной политики хранятся в БД/конфигурации с валидацией.

## Overrides

Исключения для конкретного клиента не должны реализовываться `if customer_id == ...`.

Нужна общая концепция временных/бессрочных override, например:
- tier override;
- redemption percentage override;
- другие будущие customer-specific rules.

Override содержит источник, автора, причину, `valid_from`, `valid_until` и audit trail.

## Транзакции

Application service задаёт transaction boundary. Пример `ConfirmOrder` в одной транзакции:
- проверяет staff session и permission;
- проверяет identification session;
- проверяет идемпотентность;
- рассчитывает cashback/redemption исключительно на backend;
- создаёт заказ;
- создаёт ledger entries;
- использует награду при необходимости;
- обновляет qualification/tier state;
- фиксирует audit/event records;
- commit.

Если любой шаг падает — не фиксируется ничего.

## Отмена заказа

`CancelOrder` не удаляет заказ и ledger entries. Он создаёт компенсирующие записи и восстанавливает связанное состояние в рамках одной транзакции.

Для barista backend дополнительно проверяет:
- операция создана этим Staff;
- прошло не более 10 минут;
- заказ ещё допускает barista cancellation.

## Конкурентность

Баллы, коды и награды требуют защиты от двойного использования. Использовать транзакции, ограничения БД и при необходимости row locking/optimistic concurrency. Нельзя реализовывать это только проверкой до отдельного commit.

## API

Префикс `/api/v1`.

API возвращает стабильные DTO и ошибки с машинным `code`, например:

```json
{
  "error": {
    "code": "INSUFFICIENT_POINTS",
    "message": "Недостаточно баллов",
    "details": {}
  }
}
```

## Интеграционный контракт

Интеграции должны работать через стабильные application contracts. Конкретный adapter не должен импортироваться в loyalty domain.

Необходимо предусмотреть:
- REST API;
- incoming/outgoing webhooks;
- idempotency keys;
- external ID mappings;
- подписываемые/аутентифицированные machine-to-machine requests;
- возможность позднее вынести event transport в очередь.

## Конфигурация

Environment variables — только инфраструктурные секреты/адреса. Бизнес-настройки, которые должен менять администратор, хранятся в БД и валидируются.

## Миграции

Все изменения схемы БД — только Alembic migrations. Приложение не должно самопроизвольно менять production schema при старте.

## Фоновые задачи

Планировщик нужен для:
- дней рождения;
- снижения tier после периода неактивности;
- будущего истечения баллов;
- истечения наград/overrides;
- уведомлений;
- периодических кампаний;
- обслуживающих задач.

Задачи должны быть идемпотентными.
