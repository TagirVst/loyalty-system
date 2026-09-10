# Архитектура V2

## Подход

На старте используем **модульный монолит**, а не микросервисы. Это проще в разработке и эксплуатации, но границы модулей проектируются так, чтобы при реальной необходимости модуль можно было вынести позже.

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
        domain/
        application/
        infrastructure/
        api/
      staff/
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

bots/
  client_bot/
  staff_bot/
  shared/

admin/

tests/
  unit/
  integration/
  e2e/

docs/
```

## Правило зависимости

```text
API/UI -> application/service -> domain -> repository interface
                                      ^
                                      |
                              infrastructure implementation
```

Domain не знает о Telegram, HTML, FastAPI или iiko.

## Модули

### customers
Профиль клиента, внешние идентификаторы, согласия, объединение дублей.

### staff
Сотрудники, роли, permissions, аутентификация.

### orders
Заказ, расчёт, подтверждение, отмена, идемпотентность.

### loyalty
Ledger баллов, баланс, правила начисления/списания, уровни и qualification.

### rewards
Типы наград, выданные награды, использование и истечение.

### campaigns
Правила акций, аудитории, условия и эффекты.

### feedback
Отзывы, идеи, обращения и обработка.

### notifications
Шаблоны, задания доставки, каналы и статусы.

### analytics
Read-модели/агрегации. Аналитика не должна менять доменные данные.

### audit
Кто, когда, откуда и что изменил.

### integrations
Адаптеры внешних систем, webhook endpoints, mapping внешних ID.

## События

Для слабого связывания модулей использовать domain/application events, например:
- `OrderConfirmed`;
- `OrderCancelled`;
- `PointsEarned`;
- `PointsRedeemed`;
- `TierChanged`;
- `RewardIssued`;
- `RewardRedeemed`;
- `CustomerBirthdayReached`.

На старте события могут обрабатываться внутри одного процесса. Интерфейс событий должен позволять позже подключить очередь без переписывания доменной логики.

## Расширяемость правил

Нельзя размазывать правила по роутам и ботам. Использовать стратегии/политики, например:

```python
class EarningPolicy(Protocol):
    def calculate(self, context: OrderContext) -> PointsResult: ...
```

Новые политики регистрируются централизованно. Настройки конкретной политики хранятся в БД/конфигурации с валидацией.

## Транзакции

Application service задаёт transaction boundary. Пример `ConfirmOrder` в одной транзакции:
- блокирует/проверяет нужные данные;
- проверяет идемпотентность;
- создаёт заказ;
- создаёт ledger entries;
- использует награду;
- фиксирует audit/event records;
- commit.

Если любой шаг падает — не фиксируется ничего.

## Конкурентность

Баллы и награды требуют защиты от двойного использования. Использовать транзакции, ограничения БД и при необходимости row locking/optimistic concurrency. Нельзя реализовывать это только проверкой `if balance >= x` до отдельного commit.

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

## Конфигурация

Environment variables — только инфраструктурные секреты/адреса. Бизнес-настройки, которые должен менять администратор, хранятся в БД и валидируются.

## Миграции

Все изменения схемы БД — только Alembic migrations. Приложение не должно самопроизвольно менять production schema при старте.

## Фоновые задачи

Планировщик нужен для:
- дней рождения;
- истечения наград/баллов;
- уведомлений;
- периодических кампаний;
- обслуживающих задач.

Задачи должны быть идемпотентными.
