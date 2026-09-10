# Admin Panel UX & Capabilities V2

## 1. Назначение

Админ-панель — основной центр управления loyalty-системой. Цель V2: почти все операционные правила программы должны меняться без правки кода и без доступа к БД.

Панель является отдельным интерфейсом над Backend API. Она не содержит самостоятельную бизнес-логику и не работает с БД напрямую.

Ключевые принципы:
- mobile/tablet friendly, но основной рабочий режим — desktop;
- быстрый глобальный поиск;
- понятные таблицы с фильтрами;
- destructive/financial actions требуют подтверждения;
- все административные изменения аудируются;
- настройки валидируются backend;
- UI показывает последствия сложных настроек до сохранения;
- архитектура допускает добавление новых ролей, модулей, филиалов и интеграций.

## 2. Авторизация администратора

В V2 администратор входит через разрешённый персональный Telegram identity.

Telegram — только текущий AuthProvider. Домен и admin UI не должны быть архитектурно привязаны к Telegram: позже можно добавить password/OAuth/SSO без переписывания loyalty-core.

Backend создаёт AdminSession/Principal и проверяет permissions на каждом защищённом endpoint.

## 3. Навигация

Основное меню:

```text
Обзор
Клиенты
Операции
Баллы
Уровни
Подарки
Акции
Сотрудники
Филиалы
Категории
Рассылки
Отзывы
Аналитика
Интеграции
Аудит
Настройки
```

Модули должны регистрировать свои admin sections, чтобы будущая Cafe Management Platform могла расширить меню без монолитного hardcode.

## 4. Dashboard / Обзор

Главная страница отвечает на вопрос «что происходит сейчас?».

Карточки:
- активные клиенты;
- новые регистрации;
- продажи через loyalty;
- сумма учтённых заказов;
- начислено баллов;
- списано баллов;
- outstanding points liability;
- выдано/использовано подарков;
- средний чек;
- redemption rate;
- cashback cost;
- активные акции;
- клиенты по уровням;
- проблемные события/ошибки интеграций.

Период: сегодня / вчера / 7 дней / 30 дней / произвольный.
Фильтр Location: вся сеть или конкретная точка.

Dashboard не должен выполнять тяжёлые OLTP-запросы напрямую; аналитические агрегаты можно позже вынести в read models/materialized views.

## 5. Глобальный поиск

Поиск из верхней панели:
- имя клиента;
- телефон;
- Telegram ID при наличии permission;
- customer ID;
- order number;
- сотрудник;
- reward/campaign.

Результаты сгруппированы по типу сущности.

## 6. Клиенты

Таблица:
- имя;
- телефон;
- текущий эффективный уровень;
- баланс баллов;
- lifetime/qualification spend;
- последняя покупка;
- доступные награды;
- статус active/blocked;
- дата регистрации.

Фильтры:
- уровень;
- баланс;
- сумма покупок;
- активность/неактивность;
- наличие подарков;
- день рождения/период;
- сегмент;
- blocked;
- location последней покупки;
- дата регистрации.

Экспорт — CSV/XLSX через backend export job, с permission и audit.

## 7. Карточка клиента

Верхняя часть:

```text
Имя
Телефон
Telegram identity
Статус
Уровень
Баланс
Lifetime spend
Последняя покупка
```

Вкладки:
- Обзор;
- Баллы;
- Покупки;
- Подарки;
- Уровень;
- Акции/сегменты;
- Уведомления;
- Изменения профиля;
- Audit.

Администратор может:
- блокировать/разблокировать loyalty;
- вручную изменить баланс через ledger adjustment с обязательной причиной;
- назначить tier override бессрочно или до даты;
- установить временный redemption limit до 100% с обязательной датой окончания;
- выдать существующую reward вручную, если permission это разрешает;
- отозвать reward с причиной;
- просмотреть заказы/возвраты;
- инициировать разрешённый refund;
- управлять сегментами/тегами;
- исправлять разрешённые профильные данные.

Нельзя напрямую редактировать `points_balance` или удалять ledger rows.

## 8. Баллы / Ledger

Отдельный финансовый журнал:
- timestamp;
- customer;
- type: earn/redeem/refund/reversal/manual/expire/campaign/etc.;
- delta;
- balance_after/read-model;
- order/reference;
- staff/admin actor;
- location;
- reason;
- correlation/idempotency id.

Фильтры по периоду, клиенту, типу, филиалу, actor, order.

Ручная корректировка:

```text
Клиент
Операция: начислить / списать
Количество
Причина — обязательно
[Предпросмотр]
[Подтвердить]
```

Backend проверяет невозможность некорректного отрицательного баланса и создаёт immutable entry.

## 9. Операции / Orders

Таблица:
- номер;
- дата;
- клиент;
- location;
- сотрудник;
- gross amount;
- rewards/discounts;
- points redeemed;
- paid amount;
- points earned;
- source manual/POS;
- status.

Карточка заказа показывает полный расчёт и explainability: какие tier/campaign/reward rules применились и почему.

Поддержать:
- full refund;
- partial refund;
- reversal history;
- external POS identifiers;
- idempotency/correlation identifiers для диагностики.

Финансовые записи не удаляются.

## 10. Частичный возврат

Архитектура V2 поддерживает частичный refund сразу.

Refund является отдельной сущностью/операцией, связанной с исходным Order. Он содержит сумму и при наличии товарной интеграции — возвращённые позиции/категории.

Backend пропорционально/по детальным правилам пересчитывает:
- фактически оплаченные деньги;
- qualification spend;
- earned points reversal;
- redeemed points restoration, если применимо;
- rewards restoration/reversal;
- tier state.

Правила округления должны быть детерминированными. Сумма всех refunds не может превысить исходный refundable amount.

Для POS providers refund может приходить извне по webhook/API с external idempotency key.

## 11. Уровни лояльности

Администратор управляет уровнями как данными, а не enum в коде.

Таблица уровня:
- название;
- порядок;
- threshold;
- cashback %;
- active;
- оформление/описание для клиента.

Можно добавлять, переименовывать, менять пороги и проценты.

Backend не позволяет создать неоднозначную лестницу порогов.

Перед публикацией изменения UI показывает impact preview, например сколько клиентов потенциально сменят уровень.

Начальные названия: Standard / Silver / Gold / Platinum, но они не hardcoded.

## 12. Tier inactivity

Настройки:
- включено/выключено;
- период неактивности, default 12 месяцев;
- шаг понижения, default 1 tier;
- минимальный tier;
- политика восстановления после возвращения клиента.

Политика восстановления должна быть configurable, поскольку ранее решено не hardcode поведение manual/automatic tier state.

Scheduler создаёт события/историю, а не тихо переписывает данные без trace.

## 13. Подарки / Reward Definitions

Reward Definition — шаблон награды.

Настройки:
- название;
- описание клиенту;
- тип;
- value/условия;
- применимые категории;
- срок жизни после выдачи;
- возможность использовать несколько;
- compatibility;
- active;
- future extensible config.

Типы V2:
- бесплатный товар/категория;
- фиксированная скидка;
- процентная скидка;
- points;
- extensible future types.

Отдельно показываются CustomerRewards: кому выдано, источник, остаток quantity, срок, status, redemption history.

## 14. День рождения

Birthday campaign — системная кампания на базе общего campaign/reward engine, а не отдельный хардкод.

Default:
- выдача за 3 дня;
- срок действия 7 дней.

Настраиваются reward, сроки, сообщение, active.

Обязательный yearly issuance key исключает повторную выдачу одному клиенту за один birthday cycle даже после изменения birth_date.

Если клиент пытается изменить дату рождения, клиентский интерфейс объясняет: дату можно изменить только один раз; уже полученный/использованный birthday reward за текущий год повторно не выдаётся.

## 15. Акции / Campaign Builder

Конструктор должен быть мощным, но не позволять произвольный код из БД.

Campaign состоит из:
- metadata;
- audience/segment conditions;
- order conditions;
- schedule;
- effects;
- priority;
- stacking policy;
- locations scope;
- status draft/scheduled/active/paused/finished.

Conditions могут включать:
- tier;
- customer segment;
- spend;
- visit/order count;
- categories;
- day/time;
- birthday;
- inactivity;
- first purchase;
- future supported predicates.

Effects:
- cashback multiplier xN;
- extra cashback percentage;
- issue reward;
- discount/reward effect;
- future typed handlers.

Campaign может быть network-wide в V2. Модель сразу поддерживает location scope, чтобы позже включить акции отдельных филиалов без миграции архитектуры.

Нужны preview/test mode: админ задаёт тестового клиента и заказ и видит, какие правила сработают.

## 16. Campaign stacking

Для кампании:
- priority;
- stackable true/false;
- compatibility/exclusivity group;
- conflict resolution policy.

UI должен предупреждать о потенциально конфликтующих активных кампаниях.

## 17. Сегменты

Поддержать динамические и ручные сегменты.

Примеры:
- новые клиенты;
- Gold/Platinum;
- не покупали N дней;
- spend > X;
- birthday upcoming;
- посетили определённый филиал;
- имеют/не имеют reward;
- custom tags.

Сегмент можно использовать в Campaign и Mailing.

Динамический сегмент хранит rule definition, а не постоянный вручную пересчитанный список.

## 18. Сотрудники

Таблица:
- имя;
- role;
- location;
- active;
- последняя staff session;
- PIN status;
- операции сегодня.

Создание сотрудника:
- имя;
- роль barista/admin;
- location;
- 6-digit PIN для barista;
- active.

PIN задаёт администратор, уникален в организации, хранится только как secure hash.

Администратор может:
- reset PIN;
- deactivate Staff;
- завершить активную StaffSession;
- сменить location;
- просмотреть операции/audit.

PIN никогда не отображается после сохранения.

## 19. Защита PIN

- ровно 6 цифр;
- uniqueness проверяет backend;
- 5 неверных попыток → lockout 5 минут;
- дальнейшие серии ошибок увеличивают задержку;
- успешный вход сбрасывает failure counter согласно security policy;
- failed login events аудируются;
- администратор может принудительно завершить сессию/reset PIN.

## 20. Staff terminals

Раздел рабочих Telegram-терминалов:
- Telegram identity/chat;
- location;
- active;
- текущая StaffSession;
- last seen;
- revoke.

Terminal — не сотрудник. Один и тот же сотрудник аутентифицируется своим PIN.

## 21. Филиалы

Location:
- название;
- адрес;
- timezone;
- active;
- external mappings;
- staff terminal;
- сотрудники.

Loyalty баланс/tiers общие по сети. location_id сохраняется в операциях и используется для аналитики/будущих location-specific campaigns.

## 22. Категории заказа

Категории настраиваются из админки уже в V2.

Поля:
- internal code;
- display name;
- active;
- sort order;
- unit/count semantics;
- external mappings future.

Примеры `drink`, `sandwich`, `dessert` — данные, не hardcoded enum.

Staff bot получает активный набор категорий с backend.

## 23. Рассылки

Администратор создаёт рассылку:
- название;
- сегмент/получатели;
- текст;
- optional media/buttons/deep link;
- send now / schedule;
- preview;
- test send;
- status/statistics.

Отделить transactional notifications от marketing communications.

Нужны consent/preferences и возможность отказаться от маркетинговых сообщений без отключения критических сервисных уведомлений.

Массовая отправка идёт через очередь/worker с rate limiting Telegram, retries и delivery status.

## 24. Отзывы

Клиентская оценка — 1–5 звёзд.

Таблица:
- rating;
- text;
- customer;
- order/location если связано;
- date;
- status;
- assigned/resolved.

Рекомендуемый workflow:
- 4–5: поблагодарить и при настроенном сценарии предложить перейти на внешний публичный отзыв;
- 1–3: не давить на публичный отзыв, отправить внутренний feedback администраторам/ответственным;
- admin может пометить обработанным и добавить внутреннюю заметку.

Порог должен быть configurable.

## 25. Аналитика

Минимальный набор:
- registrations;
- active customers;
- repeat rate;
- purchase frequency;
- average check;
- revenue represented in loyalty;
- points issued/redeemed/outstanding;
- redemption rate;
- reward issuance/redemption;
- campaign performance;
- tier distribution/movement;
- inactivity/churn cohorts;
- birthday campaign;
- location comparison;
- staff operations;
- refund/cancellation rate;
- feedback rating/NPS-like derived indicators if needed.

Фильтры: период/location/tier/campaign/segment.

Архитектура аналитики должна позволять позже подключить BI/read warehouse без изменения transactional core.

## 26. Интеграции

Admin раздел показывает providers/connections, а не встраивает iiko в core.

Для каждого connector:
- provider;
- status;
- locations mappings;
- credentials reference (секреты не показывать обратно);
- last sync/webhook;
- errors;
- retry/reconnect;
- external mappings.

Будущие providers: iiko, RKeeper, custom POS, internal Cafe Platform.

Все inbound financial events требуют external id/idempotency.

## 27. Audit Log

Неизменяемый журнал административных/важных staff действий:
- actor principal;
- action;
- entity type/id;
- timestamp;
- location/context;
- before/after safe diff;
- reason;
- correlation id;
- source/ip/device metadata где уместно.

Особенно аудируются:
- points adjustment;
- refunds;
- customer block;
- tier override;
- redemption override;
- reward issue/revoke;
- campaign changes;
- staff/PIN/session changes;
- terminal changes;
- integration configuration;
- permissions/settings.

Секреты/PIN hashes/tokens не должны попадать в audit payload.

## 28. Настройки программы

Настраиваемые параметры:
- default redemption limit = 30%;
- point value = 1 ₽;
- point expiry disabled now, future policy prepared;
- customer identification code TTL = 90 sec;
- barista cancellation window = 10 min;
- birthday issue offset/default validity;
- inactivity period;
- cashback rounding = floor to integer point;
- feedback thresholds;
- notification preferences/policies;
- campaign defaults;
- security/session policies where safe.

Настройки versioned. Финансово влияющее изменение не должно задним числом менять уже проведённые операции.

## 29. Денежные правила V2

Зафиксировано:
- расчёты не используют binary float;
- деньги хранятся в integer minor units или Decimal с строгой precision policy;
- points — целые;
- cashback округляется вниз до целого point;
- при использовании хотя бы одного point cashback = 0;
- без points cashback считается от реально оплаченной суммы после применимых скидок/rewards;
- стандартный лимит redemption 30% считается от суммы после скидок/rewards, но до списания points;
- qualification spend следует отдельной policy и не равен cashback base автоматически.

## 30. Refund rules

V2 закладывает full и partial refund.

Нельзя просто `DELETE Order` или изменять ledger entry.
Refund создаёт compensating financial/domain records.

Backend обязан уметь объяснить результат refund: сколько points вернулось, сколько начисления сторнировано, какая qualification сумма уменьшилась, какие rewards восстановлены/погашены.

## 31. Permissions

Хотя в V2 роли только `admin` и `barista`, проверки должны опираться на permissions/capabilities, а не `if role == admin` по всему коду.

Примеры permissions:
- customers.read;
- customers.block;
- points.adjust;
- orders.refund;
- tiers.manage;
- rewards.manage;
- campaigns.manage;
- staff.manage;
- locations.manage;
- mailings.manage;
- feedback.manage;
- analytics.read;
- integrations.manage;
- audit.read;
- settings.manage.

Это позволит позже добавить manager/marketer/accountant без переписывания application services.

## 32. UX финансовых изменений

Для points adjustment, refund, tier/redemption override и подобных действий:
1. заполнить форму;
2. backend validation;
3. показать preview последствий;
4. явное подтверждение;
5. commit;
6. success screen с reference id;
7. audit event.

Для особо рискованных операций позже можно включить step-up auth/dual approval без изменения command contracts.

## 33. Responsive UX

Desktop:
- sidebar;
- таблицы;
- detail drawer/page;
- быстрые filters/saved views.

Mobile/tablet:
- collapsible navigation;
- карточки вместо широких таблиц;
- sticky primary action;
- никаких критичных hover-only controls.

Админка не должна зависеть от Telegram WebView и может работать как обычное защищённое web-приложение.

## 34. Архитектурная граница

```text
Admin Web UI
    ↓
Admin API / Application Commands & Queries
    ↓
Domain modules
    ↓
Repositories / DB / Events
```

Запрещено:
- SQL из frontend;
- бизнес-правила только в JavaScript UI;
- изменение баланса прямым UPDATE;
- POS-specific conditionals в loyalty services;
- Telegram-specific identity logic внутри domain entities.

## 35. Готовность к Cafe Management Platform

Admin shell должен в будущем принять дополнительные модули кафе: inventory, recipes, production, purchasing, finance, staff scheduling, full orders, analytics и integrations.

Loyalty-разделы не должны требовать отдельной второй админки после объединения проекта. Предпочтительно единое navigation/module registry и общий Auth/Permission layer.

## 36. Вопросы, которые ещё нужно закрыть

Перед окончательной фиксацией application rules необходимо решить:
- что происходит с inactivity penalty после первой покупки вернувшегося клиента;
- точные стартовые thresholds и cashback % Standard/Silver/Gold/Platinum;
- мигрируем ли реальные V1 customers/points/history или V2 стартует с чистой БД;
- нужна ли multi-organization/tenant модель уже как архитектурная основа будущей Cafe Platform;
- валюта: только RUB в V2 или сразу currency field;
- кто кроме admin получает внутренние уведомления о плохих отзывах;
- нужен ли двухэтапный approve для крупных ручных корректировок/возвратов в будущем.
