# Безопасность и качество V2

## Авторизация

Клиентские, staff, admin и integration credentials разделены.

Backend проверяет permission для каждого защищённого действия. Скрытая кнопка в UI не является защитой.

## Telegram

Telegram ID используется только как подтверждённая внешняя identity. Бот не передаёт произвольный `staff_id` как доказательство личности.

Внутренний trusted bot/service должен аутентифицироваться перед backend, а backend сопоставляет Telegram identity с Staff/Customer.

## API

- TLS в production;
- rate limiting для чувствительных endpoints;
- ограничение размеров payload;
- строгая Pydantic-валидация;
- CORS только для нужных origins;
- secure cookies для web admin;
- CSRF-защита для cookie-based write operations;
- request/correlation ID;
- отсутствие stack trace/секретов в публичных ошибках.

## Секреты

Токены Telegram, пароли, DB credentials, API keys не коммитятся в Git. Используются secrets/environment injection. В репозитории только `.env.example` без реальных значений.

## Пароли

Если есть локальные пароли сотрудников/админов — только современный password hash (Argon2id/bcrypt с корректной конфигурацией), никогда plaintext.

## Аудит

Обязательно логируются:
- ручное изменение баллов;
- выдача/отзыв награды;
- отмена заказа;
- изменение бизнес-настроек;
- изменение ролей/прав;
- административное изменение клиента;
- действия интеграций, влияющие на loyalty.

## Денежно-подобные операции

Баллы рассматриваются как ценная величина. Нужны:
- транзакционность;
- идемпотентность;
- защита от race condition;
- audit trail;
- компенсирующие операции вместо удаления истории.

## Тестирование

### Unit
Доменные правила: начисление, списание, tiers, rewards, campaigns.

### Integration
PostgreSQL + repositories + transactions + API.

### E2E
Критические сценарии:
- регистрация;
- заказ с начислением;
- заказ со списанием;
- недостаточный баланс;
- повтор idempotency request;
- параллельная попытка двойного списания;
- выдача/использование награды;
- birthday reward один раз;
- отмена заказа;
- запрет операции без permission.

## CI

На каждый PR:
- formatter/linter;
- type checking;
- tests;
- migration sanity check;
- dependency/security scan по возможности;
- запрет merge при падении обязательных checks.

## Наблюдаемость

Структурированные logs без персональных секретов, health/readiness endpoints, метрики ошибок/latency и идентификатор запроса для трассировки.

## Backup

PostgreSQL backup по расписанию + проверяемая процедура restore. Backup считается рабочим только если восстановление периодически тестируется.
