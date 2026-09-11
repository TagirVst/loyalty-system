# Интеграция Loyalty System V2 с iikoWeb / iikoCloud

Дата исследования: **2026-09-11**  
Статус документа: **архитектурная спецификация интеграции для v0.1 prerelease**  
Целевая конфигурация: **iikoWeb, решение/тариф «Кафе», Россия**

## 1. Цель документа

Этот документ фиксирует, как Loyalty System V2 должна интегрироваться с iiko в конфигурации, где кафе работает через iikoWeb/iikoCloud, а наша система остаётся самостоятельным loyalty-сервисом.

Главный принцип: **не привязывать доменную модель Loyalty System V2 к конкретной версии iiko API**. iiko подключается как внешний POS/provider через уже существующий provider-neutral integration layer.

Документ разделяет:

1. что подтверждено текущими официальными материалами iiko;
2. что технически доступно через iikoCloud API;
3. что не следует считать автоматически включённым в тариф «Кафе»;
4. как данные iiko должны отображаться на наши сущности;
5. какую интеграцию можно реализовать только через Cloud API, а где для полноценной кассовой лояльности потребуется iikoFront/сертифицированный connector или отдельное согласование с iiko;
6. рекомендуемый план реализации.

---

## 2. Что представляет собой текущий тариф iiko «Кафе»

На публичной странице iiko для формата «Кафе» на дату исследования указана стоимость **5 000 ₽/мес** за заведение и уровень управления бизнесом **ОПТИ**.

В опубликованный набор возможностей входят, в частности:

- одна касса;
- один кухонный экран;
- управление меню и ценами;
- техкарты, нормы закладки и себестоимость;
- складской учёт и мобильная инвентаризация;
- прогнозирование продаж;
- отчёты и дашборды;
- конструктор отчётов;
- сотрудники, расписание и контроль явки;
- доставка и агрегаторы;
- электронные карты лояльности;
- iikoWeb как облачный веб-офис.

Важно: на публичной странице тарифа **Cloud API не указан как гарантированно включённая в 5 000 ₽/мес функция**. Поэтому доступ к API нельзя считать частью тарифа без дополнительной проверки в конкретном аккаунте iiko или подтверждения от iiko/обслуживающего партнёра.

### Практическое правило для нашего проекта

Перед разработкой production-подключения необходимо получить от владельца iiko-аккаунта фактическое подтверждение:

- доступен ли в iikoWeb раздел интеграций/API;
- можно ли создать API key;
- требуется ли отдельная лицензия/connector/договор;
- доступна ли разработчику регистрация приложения;
- какие scopes/организации открыты приложению.

Если API не входит в текущую коммерческую конфигурацию, наша архитектура **не меняется**: меняется только способ/лицензия подключения provider `iiko`.

---

## 3. Актуальное состояние iikoWeb

Текущая база знаний iiko выделяет iikoWeb как веб-офис. Старые отдельные страницы тарифов Start/Pro/Enterprise помечены архивными и не обновляются с мая 2026 года; актуальная продуктовая линейка публикуется по форматам бизнеса — в нашем случае «Кафе».

iikoWeb также содержит настройки ресторанов, терминалов и внешних меню. В документации iiko указано, что:

- в карточке ресторана определяется основной склад;
- отображаются подключённые кассовые терминалы;
- можно получать код подключения терминала для iikoFront;
- внешние меню могут иметь расписание действия;
- внешнее меню используется API-сервисами, например сайтом или доставкой.

Это важно для mapping нашей `Location` к конкретной организации/точке iiko и для будущего sync меню.

---

## 4. Виды API/интеграций iiko, которые нельзя смешивать

У iiko есть несколько разных интеграционных уровней. Для нашей системы важно явно различать их.

### 4.1. iikoCloud API / iikoTransport

Облачный HTTP API на домене:

`https://api-ru.iiko.services`

Он подходит для server-to-server интеграции и не требует установки нашего backend непосредственно на кассу.

Типичные задачи:

- получение доступных организаций;
- получение terminal groups;
- получение номенклатуры/внешнего меню;
- стоп-листы;
- типы оплат и скидок;
- создание внешних заказов;
- получение/изменение заказов и доставок;
- работа с гостями и частью loyalty API, если соответствующие возможности доступны аккаунту;
- отправка некоторых команд/уведомлений.

### 4.2. iikoFront API / plugin

Это API/SDK для плагинов, работающих непосредственно в кассовом приложении iikoFront.

Этот слой нужен, когда требуется вмешиваться непосредственно в кассовый UX или жизненный цикл заказа iikoFront в реальном времени.

Примеры:

- показать оператору нашу форму/кнопку;
- получить событие изменения/закрытия локального заказа;
- выполнить кастомную loyalty/payment операцию непосредственно из iikoFront;
- обеспечить сценарий, который Cloud API не предоставляет для обычной продажи в зале.

iikoWeb содержит «Конфигуратор плагинов iikoFront», то есть сама веб-конфигурация iiko допускает управление установленными кассовыми plugins.

### 4.3. Сертифицированный iikoConnector

В магазине iiko существует отдельная категория интеграционных модулей, в том числе большое количество внешних CRM/loyalty систем. Это важное подтверждение того, что **внешняя система лояльности является штатным сценарием экосистемы iiko**, но часто подключается через отдельный connector/licensing path, а не просто «включается» в базовом тарифе кафе.

Для Loyalty System V2 это означает, что у нас должны быть два возможных deployment path:

1. **Cloud-only integration** — если необходимые события и операции предоставляются аккаунту через iikoCloud API;
2. **Cloud + iikoFront/connector integration** — если требуется полноценная работа нашей лояльности внутри стандартного кассового checkout iikoFront.

---

## 5. Критически важное изменение авторизации iiko API в 2026 году

11 апреля 2026 года iiko официально объявила переход на новую схему авторизации API.

Официально заявлено:

- с **1 июня 2026** старым способом нельзя создавать новые API keys;
- с **29 августа 2026** старый метод авторизации полностью отключается;
- интеграционные сервисы необходимо регистрировать на портале разработчика iiko.

Следовательно, наша production-интеграция **не должна реализовываться только через старый `/api/1/access_token` с одним `apiLogin`**.

Текущая интеграционная реализация должна быть рассчитана на новую схему приложения. По текущим developer implementations экосистемы iiko она использует регистрацию приложения (`appId`, `clientSecret`) совместно с API key и endpoint нового поколения `/api/v2/access_token`.

### Требование к нашей системе

Секреты iiko должны храниться вне БД открытым текстом и вне Git:

- `IIKO_API_KEY` / API login;
- `IIKO_APP_ID`;
- `IIKO_CLIENT_SECRET`;
- при необходимости region/base URL.

Production secret storage может быть env/secret manager. В БД допускается хранить только provider configuration без самого `clientSecret` либо ссылку на секрет.

Token должен кэшироваться до истечения срока и обновляться централизованным `IikoAuthClient`.

Нельзя получать новый token на каждый business request.

---

## 6. Что iikoCloud API даёт полезного именно нашей Loyalty System V2

Ниже — минимальный набор возможностей, который имеет смысл использовать.

### 6.1. Organizations

Назначение:

- определить список организаций iiko, разрешённых текущему приложению;
- связать iiko organization с нашей `Organization`/`Location`.

Ожидаемый provider identifier:

- `provider = "iiko"`;
- `external_organization_id = <UUID iiko>`.

Нельзя определять tenant только по имени заведения.

### 6.2. Terminal groups

Используется для:

- определения кассовой группы/точки;
- маршрутизации внешнего заказа;
- mapping iiko terminal group → наша `Location`.

В нашей системе должен храниться устойчивый external mapping, например:

```text
Organization
  └─ Location
       ├─ provider = iiko
       ├─ iiko_organization_id
       └─ iiko_terminal_group_id
```

Один `Location` не должен автоматически доверять terminal group, пришедшей из webhook/request: mapping проверяется по нашей БД.

### 6.3. Номенклатура

Cloud API предоставляет получение номенклатуры организации. Поддерживается revision-based модель, позволяющая после первой полной загрузки получать изменения, а не каждый раз импортировать всё меню с нуля.

Для Loyalty V2 **не нужно копировать всю iiko номенклатуру в качестве собственной POS-базы**.

Нам достаточно provider catalog cache/mapping для:

- `product_id`;
- группы/категории;
- названия;
- цены/размера при необходимости;
- признака активности;
- внешнего menu ID/revision;
- mapping продукта в loyalty category.

### 6.4. Внешнее меню

Для пользовательских каналов (будущий Mini App, сайт, доставка) предпочтительно рассматривать API внешнего меню, потому что iikoWeb позволяет отдельно определять внешнее меню и расписание его действия.

Внешнее меню лучше полного внутреннего справочника, когда нашей системе нужно именно **то, что разрешено показывать/продавать гостю**, а не технологическая номенклатура кухни.

### 6.5. Stop lists

Стоп-лист полезен будущему Mini App/ordering module.

Для текущей loyalty-only версии он не является критическим, но provider interface должен позволять получать availability, чтобы в будущем не менять архитектуру.

### 6.6. Payment types / discounts

Нужны при создании внешних заказов и при согласовании того, как iiko будет видеть оплату/скидку, созданную сторонней системой.

Мы не должны автоматически преобразовывать наши `points` в «скидку iiko» без утверждённого кассового сценария: у points есть собственный финансовый ledger и refund semantics.

### 6.7. Customer / loyalty API iiko

iiko Cloud API содержит методы для получения информации о гостях и loyalty данных. Но в нашей архитектуре на первом этапе **iiko не должна становиться source of truth для Loyalty System V2**.

Source of truth остаются:

- `Customer`;
- `PointsAccount`;
- immutable `PointsLedgerEntry`;
- `CustomerReward`;
- `CustomerLoyaltyState`;
- Campaign/Reward engine нашей системы.

Иначе мы потеряем наши правила cashback, debt, historical snapshots, refund semantics, manual overrides и аудит.

Допустимый вариант — синхронизировать внешний iiko guest ID как дополнительную identity/mapping.

---

## 7. Что Cloud API само по себе НЕ гарантирует

Это главный архитектурный риск.

Наличие iikoCloud API не означает автоматически, что мы можем через него встроить стороннюю loyalty систему в **каждую обычную продажу, созданную кассиром непосредственно в iikoFront**, до момента оплаты.

Для полноценного сценария нашей лояльности на кассе нужны следующие возможности:

1. получить текущий заказ iikoFront до оплаты;
2. определить клиента нашей системы;
3. показать допустимые rewards/points;
4. рассчитать сумму списания;
5. передать результат обратно в iiko как разрешённую операцию оплаты/скидки;
6. получить достоверное событие окончательного закрытия/отмены/refund;
7. не начислить loyalty дважды при retry/offline/reconnect.

Если эти события/операции не предоставляются конкретной Cloud API лицензией, нужен **iikoFront plugin или официальный connector path**.

Это не недостаток нашей архитектуры. Именно поэтому V2 уже содержит generic integration provider вместо прямой зависимости от Cloud API.

---

## 8. Рекомендуемая архитектура iiko provider

Добавить provider package примерно следующей структуры:

```text
src/loyalty_v2/integrations/iiko/
    auth.py
    client.py
    models.py
    mapping.py
    catalog_sync.py
    order_adapter.py
    webhook_adapter.py
    errors.py
```

Не размещать iiko-specific поля в `OrderService`, `RefundService`, `PointsService`.

### Поток

```text
iikoCloud / iikoFront connector
          │
          ▼
      IikoAdapter
          │
          ▼
 IntegrationOrderService
          │
          ▼
   обычный OrderService
          │
          ├─ RewardEngine
          ├─ Points ledger
          ├─ Tier engine
          ├─ Milestones
          └─ Audit
```

То есть заказ из iiko должен пройти **тот же business pipeline**, что manual Telegram order.

---

## 9. Mapping iiko → Loyalty System V2

| iiko | Loyalty System V2 | Правило |
|---|---|---|
| organization ID | Organization / provider mapping | immutable external ID |
| restaurant/terminal group | Location | mapping задаётся администратором |
| terminal | StaffTerminal или external terminal mapping | не создавать автоматически без проверки |
| order ID | ExternalOrderMapping.external_order_id | unique per provider/org |
| correlation ID | IntegrationWebhookInbox / operation metadata | для диагностики, не business ID |
| product ID | provider product mapping | не наш primary key |
| group/category | SaleCategory mapping | явное configurable mapping |
| guest ID | CustomerAuthIdentity/external identity mapping | опционально |
| phone | Customer phone | только после нормализации/verification policy |
| payment type | external payment metadata | не points ledger |
| discount | external order adjustment | хранить отдельно от points |
| order status | external status snapshot | confirmed/refunded преобразуются идемпотентно |

---

## 10. Customer identification на кассе

Для нашей системы рекомендуется не делать номер телефона основным кассовым идентификатором.

Текущий V2 flow уже имеет безопасную модель:

1. клиент открывает Telegram bot;
2. получает 5-значный код на 90 секунд;
3. кассир вводит код;
4. backend разрешает code → customer;
5. Loyalty System считает доступные points/rewards.

При интеграции с iikoFront этот сценарий можно сохранить почти без изменений.

Позже вместо 5-значного кода могут использоваться QR/NFC, не меняя loyalty engine.

### Почему это лучше прямого поиска по телефону

- не раскрывает телефон кассиру без необходимости;
- подтверждает физическое/логическое присутствие клиента;
- снижает риск списания чужих points;
- не требует синхронного создания одинаковой guest database в iiko и у нас;
- уже совместимо с нашей `IdentificationSession`.

---

## 11. Как должен выглядеть идеальный checkout с iiko

### Вариант A — полноценный iikoFront connector

```text
1. Кассир создаёт заказ в iikoFront.
2. Нажимает «Loyalty / Код клиента».
3. Вводит 5-значный код/сканирует QR.
4. Connector → Loyalty API: identify customer.
5. Connector передаёт состав/сумму заказа.
6. Loyalty API возвращает OrderPreview:
   - tier;
   - balance;
   - max redeemable points;
   - rewards;
   - campaign effects;
   - expected cashback.
7. Кассир выбирает points/reward.
8. Connector повторно запрашивает quote.
9. iiko применяет допустимый payment/discount representation.
10. После успешного закрытия чека connector отправляет final event.
11. Loyalty System идемпотентно подтверждает Order.
12. При отмене/refund iiko event вызывает RefundService.
```

### Критическое правило

**Не подтверждать loyalty order в момент нажатия «Применить».**

Подтверждение points/cashback должно происходить только после достоверного факта успешного закрытия продажи в iiko. До этого используется draft/quote/reservation-like state.

---

## 12. Cloud-only сценарий

Cloud-only интеграция возможна раньше полной кассовой интеграции и уже полезна.

### Этап 1

- проверить новую authorization scheme;
- получить organizations;
- получить terminal groups;
- сохранить mappings;
- health check API.

### Этап 2

- sync nomenclature/external menu;
- sync categories/product mappings;
- stop lists при необходимости.

### Этап 3

- поддержать external order channel, если мы создаём заказ сами, например из будущего Telegram Mini App/сайта;
- такой заказ отправлять в iiko и параллельно вести loyalty через наш стандартный pipeline.

Этот вариант **не требует**, чтобы наша loyalty сразу была встроена во все обычные кассовые продажи.

---

## 13. Сценарий внешнего заказа из нашей системы в iiko

Когда появится собственный ordering channel:

```text
Customer/Mini App
   ↓
Our Order API
   ↓
Loyalty quote
   ↓
IikoAdapter.create_external_order()
   ↓
iikoCloud
   ↓
external_order_id/correlation
   ↓
ExternalOrderMapping
   ↓
confirmed iiko state
   ↓
OrderService.confirm()
```

### Idempotency

Для каждого внешнего заказа создаётся стабильный key:

`iiko:create-order:<our_order_uuid>`

Повторная отправка после timeout не должна создавать второй заказ.

Если iiko возвращает correlation ID до окончательной обработки, его нужно хранить и опрашивать/проверять результат вместо создания нового заказа.

---

## 14. Webhooks, polling и фактические события

Нельзя проектировать интеграцию, предполагая наличие webhook для любого события iiko, пока конкретный endpoint/event contract не подтверждён текущей документацией/выданными scopes.

Наш integration layer уже поддерживает webhook inbox, поэтому стратегия должна быть:

1. если iiko предоставляет push event для нужного события — принимаем webhook;
2. сохраняем raw event/idempotency key в `IntegrationWebhookInbox`;
3. отвечаем быстро;
4. business processing делаем идемпотентно;
5. если push event отсутствует — используем bounded polling/status query;
6. для кассовых локальных событий, недоступных Cloud API, используем iikoFront connector.

---

## 15. Refund/cancel

Наша система не должна самостоятельно предполагать refund только по уменьшению суммы заказа.

Нужен внешний immutable reference:

- iiko order ID;
- iiko refund/cancel operation ID или эквивалент;
- timestamp;
- amount;
- item/category breakdown, если доступен.

После этого вызывается штатный `RefundService`, который уже умеет:

- full/partial refund;
- вернуть spent points;
- отменить earned cashback;
- создать points debt, если cashback уже потрачен;
- уменьшить qualification;
- пересчитать tier;
- откатить milestones;
- восстановить reward при поддерживаемом full-refund lifecycle.

iiko adapter не должен самостоятельно менять balance.

---

## 16. Категории и milestone rewards

В iiko есть собственные product/group IDs. Нельзя использовать название группы как стабильный ID.

Нужна таблица mapping:

```text
provider_category_mapping
- organization_id
- location_id nullable
- provider = iiko
- external_group_id
- sale_category_id
- active
```

Пример:

```text
iiko group «Кофе» UUID ... → SaleCategory COFFEE
iiko group «Сэндвичи» UUID ... → SaleCategory SANDWICH
```

Именно `SaleCategory` продолжает использовать наш milestone engine.

При переименовании группы в iiko mapping не ломается.

---

## 17. Кто является source of truth

### iiko — source of truth для

- факта POS-продажи/фискального checkout;
- состава POS-заказа;
- продуктовых IDs;
- факта кассовой отмены/refund;
- доступности/stop-list;
- POS terminal/restaurant identifiers.

### Loyalty System V2 — source of truth для

- customer loyalty identity;
- points balance;
- immutable points ledger;
- cashback rules;
- tiers;
- qualification spend;
- rewards;
- campaigns;
- individual overrides;
- points debt;
- loyalty audit.

### Запрещено

- «сверять» наш balance путём безусловного копирования баланса из iiko;
- пересчитывать наш ledger из текущего iiko balance;
- напрямую изменять points из iiko adapter;
- считать имя/телефон/customer ID iiko нашим tenant key;
- начислять cashback до final sale confirmation.

---

## 18. Security

### Secrets

Не хранить в Git:

- API key;
- appId, если policy iiko считает его credential;
- clientSecret;
- access token.

`clientSecret` всегда считать секретом.

### Token

- token cache только server-side;
- не передавать token Telegram bot/client;
- refresh до expiration;
- при 401 выполнить один controlled refresh/retry;
- не делать бесконечный retry.

### Logging

Разрешено логировать:

- provider;
- organization ID;
- endpoint name;
- HTTP status;
- iiko correlation ID;
- наш request/idempotency ID;
- duration.

Запрещено логировать:

- clientSecret;
- bearer token;
- полный API key;
- PIN;
- customer identification code;
- чувствительные customer данные без необходимости.

---

## 19. Resilience

### Timeout

Все iiko HTTP calls должны иметь конечный timeout.

### Retry

Retry допустим для:

- network timeout;
- 429;
- части 5xx.

Retry запрещён без idempotency strategy для mutation endpoint.

### Circuit breaker

После серии ошибок iiko provider временно переводится в degraded state, но наш backend остаётся доступен.

`/ready` не должен обязательно становиться полностью красным из-за кратковременной недоступности iiko, если core loyalty database работает. Для provider нужен отдельный operational status.

### Reconciliation

Нужен периодический job:

```text
external order mappings
    ↕
iiko final states
    ↕
our confirmed/refunded orders
```

Mismatch должен попадать в admin operational report, а не исправляться тихо.

---

## 20. Что следует добавить в наши provider contracts

Текущая V2 foundation уже имеет generic integration clients/webhook inbox/external order mapping. Для iiko рекомендуется развивать интерфейс примерно так:

```python
class PosProvider:
    async def health(self) -> ProviderHealth: ...
    async def organizations(self) -> list[ExternalOrganization]: ...
    async def locations(self) -> list[ExternalLocation]: ...
    async def catalog_revision(self, ...) -> CatalogSnapshot: ...
    async def availability(self, ...) -> AvailabilitySnapshot: ...
    async def create_order(self, command: ExternalOrderCommand) -> ExternalOrderResult: ...
    async def get_order(self, external_order_id: str) -> ExternalOrderState: ...
```

Для кассового connector path дополнительно:

```python
class PosCheckoutBridge:
    async def preview_loyalty(self, order: PosOrderSnapshot) -> LoyaltyPreview: ...
    async def confirm_sale(self, event: PosSaleClosed) -> None: ...
    async def refund_sale(self, event: PosRefunded) -> None: ...
```

`PosCheckoutBridge` — наш interface. Реализация может быть iikoFront plugin, connector service или иной поддерживаемый iiko механизм.

---

## 21. Рекомендуемые этапы реализации

### Phase IIKO-0 — коммерческая/доступная конфигурация

До написания кода получить из реального iikoWeb:

- screenshot/название раздела интеграции;
- возможность создать API key;
- app registration credentials;
- organization list;
- список разрешённых API scopes;
- подтверждение тарификации Cloud API/connector.

**Definition of Done:** есть тестовые credentials без production secret в Git.

### Phase IIKO-1 — Cloud connectivity

Реализовать:

- `IikoAuthClient` новой схемы;
- organizations;
- terminal groups;
- provider health;
- encrypted/secret configuration;
- API error normalization;
- correlation IDs;
- rate limit handling.

**DoD:** integration test получает organization и terminal group из sandbox/real test account.

### Phase IIKO-2 — Catalog

Реализовать:

- nomenclature revision sync;
- external menu sync при необходимости;
- category mapping;
- stop-list read;
- admin diagnostics.

**DoD:** продукт/категория iiko стабильно отображается в нашу `SaleCategory`.

### Phase IIKO-3 — External orders

Использовать наш существующий IntegrationOrderService и ExternalOrderMapping.

**DoD:** один наш order создаёт ровно один iiko order даже при retry.

### Phase IIKO-4 — Native iikoFront loyalty checkout

После подтверждения подходящего iikoFront/connector API:

- customer code/QR;
- preview;
- reward/points selection;
- final sale callback;
- cancel/refund callback;
- offline/error UX.

**DoD:** кассир не открывает отдельный staff Telegram flow для обычной продажи.

### Phase IIKO-5 — Reconciliation / production cutover

- reconciliation job;
- metrics;
- alerts;
- duplicate/missing event tests;
- load/concurrency test;
- production runbook.

---

## 22. Что можно сделать уже сейчас без iiko credentials

Можно реализовать безопасно:

- provider interfaces;
- auth config schema без секретов;
- DTO/models;
- mapping tables;
- idempotency architecture;
- fake iiko provider;
- contract tests;
- reconciliation framework;
- admin screens/API для provider mappings.

Не следует без реальных credentials/актуального API contract угадывать:

- точный payload новой authorization scheme;
- полный список scopes конкретного аккаунта;
- webhook event schemas;
- native POS sale event contract;
- способ применения нашей loyalty как payment/discount в iikoFront;
- коммерческую стоимость API/connector для конкретного тарифа.

---

## 23. Что нужно запросить у iiko/партнёра

Перед Phase IIKO-1 отправить один конкретный запрос:

> Используем iikoWeb, решение «Кафе». Разрабатываем собственную внешнюю систему лояльности. Нужен server-to-server доступ iikoCloud API и в дальнейшем интеграция с обычными продажами iikoFront: получение состава заказа до оплаты, применение внешнего списания/скидки, подтверждение закрытия продажи и обработка возвратов. Просим подтвердить, какие лицензии/connector нужны для нашей конфигурации, как создать API key и developer application, какие API/scopes доступны и какой рекомендуемый механизм используется для внешней loyalty в iikoFront.

Отдельно уточнить:

1. входит ли Cloud API в текущий тариф или оплачивается отдельно;
2. нужен ли iikoConnector для собственной loyalty системы;
3. нужен ли отдельный iikoFront API license;
4. можно ли получать reliable final event обычного кассового заказа;
5. можно ли зарегистрировать собственный payment/discount/loyalty operation;
6. поддерживается ли официальный webhook для sale/refund;
7. есть ли sandbox/test organization.

---

## 24. Итоговое решение для Loyalty System V2

Для нашего проекта **iiko должна быть POS/provider, а не владельцем loyalty business logic**.

Правильная конечная архитектура:

```text
                         ┌─────────────────────┐
                         │      iikoWeb        │
                         │ menu/config/storage │
                         └──────────┬──────────┘
                                    │
                             iikoCloud API
                                    │
                                    ▼
┌──────────────┐            ┌───────────────┐
│ Telegram /   │            │  IikoAdapter  │
│ Mini App     │            └───────┬───────┘
└──────┬───────┘                    │
       │                            ▼
       │                   Integration layer
       │                            │
       └──────────────┬─────────────┘
                      ▼
              Loyalty System V2
          ledger / tiers / rewards /
          campaigns / refunds / audit
                      ▲
                      │
             iikoFront connector
          (когда нужен native POS UX)
```

Cloud API использовать для того, что является server-to-server задачей. Для realtime native checkout не пытаться насильно решить всё Cloud API, если iiko для этого предусматривает Front API/connector.

Такой подход позволяет начать с iikoWeb «Кафе», а в дальнейшем подключить другую POS-систему без переписывания loyalty core.

---

## 25. Источники, проверенные 2026-09-11

### Официальные iiko

1. Тариф/решение «Кафе»:  
   https://iiko.ru/solutions/cafe/

2. Общая актуальная база знаний iiko:  
   https://ru.iiko.help/home/ru-ru/

3. Настройки ресторанов iikoWeb, терминалы и внешние меню:  
   https://ru.iiko.help/article/iikoweb/stores

4. Общие настройки iikoWeb / configurator plugins iikoFront:  
   https://ru.iiko.help/article/iikoweb/general-settings

5. Официальное объявление о смене API authorization в 2026 году:  
   https://iiko.ru/news/perehod-na-novuyu-shemu-avtorizaczii-v-api/

6. Страница договоров iiko, включая iikoCloud и API для технологических партнёров:  
   https://iiko.ru/oferta/

7. Магазин официальных integration connectors iiko:  
   https://store.iiko.ru/connectors

8. Cloud API documentation entry point:  
   https://api-ru.iiko.services/docs

### Дополнительная техническая проверка

Для проверки существующих endpoint names и текущего developer ecosystem использовались открытые API clients/wrappers. Они **не являются источником коммерческих условий** и не должны заменять текущую официальную API schema после выдачи credentials.

---

## 26. Решение для v0.1 prerelease

В `v0.1.0rc1` **iiko-specific production code сознательно не добавляется без реального API access**.

В релиз включается эта спецификация, а существующий generic integration foundation считается подготовленным к `IikoAdapter`.

Это позволяет не закрепить в коде устаревшую/неподтверждённую схему iiko и одновременно иметь готовый технический план подключения сразу после получения credentials и подтверждения лицензии.
