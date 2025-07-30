# КЛИЕНТСКИЙ БОТ
WELCOME_MSG = "Добро пожаловать в программу лояльности кофейни! Жмите 'Начать' для регистрации."
REGISTER_PHONE = "Пожалуйста, отправьте свой номер через кнопку ниже."
REGISTER_FIRSTNAME = "Введите ваше имя:"
REGISTER_LASTNAME = "Введите вашу фамилию:"
REGISTER_BIRTHDATE = "Введите вашу дату рождения (ДД.ММ.ГГГГ):"
REGISTER_CONFIRM = "Проверьте данные и подтвердите регистрацию."

REGISTRATION_SUCCESS = "Вы успешно зарегистрированы! Добро пожаловать 🎉"

PROFILE_TEMPLATE = (
    "Профиль:\n"
    "Имя: {first_name}\n"
    "Фамилия: {last_name}\n"
    "Телефон: {phone}\n"
    "Дата рождения: {birth_date}\n"
    "Уровень лояльности: {loyalty_status}\n"
    "Баллы: {points}\n"
    "Напитков куплено: {drinks_count}\n"
    "Сэндвичей куплено: {sandwiches_count}\n"
    "Подарков (напитки): {gift_drinks}\n"
    "Подарков (сэндвичи): {gift_sandwiches}"
)

CODE_GENERATED = (
    "Вы можете накопить или списать ваши бонусы, назвав этот код бариста: {code}\n"
    "Код действует 90 секунд."
)

CODE_EXPIRED = "Срок действия кода истек. Сгенерируйте новый код."
CODE_INVALID = "Некорректный код или он уже использован."

FEEDBACK_MENU = "Обратная связь:\nВыберите действие:"
FEEDBACK_THANKS_POSITIVE = "Спасибо! Пожалуйста, разместите отзыв на наших страницах: ..."
FEEDBACK_THANKS_NEGATIVE = "Расскажите подробнее, что можно улучшить:"
FEEDBACK_SENT = "Спасибо за ваш отзыв!"

IDEA_SENT = "Спасибо! Ваша идея отправлена руководству."

BIRTHDAY_CONGRATS = "С Днем рождения! 🎉 Вам подарок от кофейни — бесплатный напиток!"

# БАРИСТА-БОТ
BARISTA_WELCOME = "Главное меню бариста."
ORDER_CODE_INPUT = "Введите 5-значный код клиента:"
ORDER_CLIENT_FOUND = "Клиент: {first_name} {last_name}. Подтвердите заказ."
ORDER_INPUT_RECEIPT = "Введите номер чека:"
ORDER_INPUT_SUM = "Введите сумму заказа (в рублях):"
ORDER_INPUT_DRINKS = "Введите количество напитков:"
ORDER_INPUT_SANDWICHES = "Введите количество сэндвичей:"
ORDER_POINTS_OR_ACCUM = "Списать или накопить баллы?"
ORDER_CONFIRM = "Подтвердить заказ?"
ORDER_SUCCESS = "Заказ успешно проведён!"
ORDER_FAIL = "Ошибка при обработке заказа!"

GIFT_SUCCESS = "Подарок успешно начислен/списан!"
GIFT_ERROR = "Ошибка: недостаточно подарков или неправильный тип."

REFUND_CONFIRM = "Подтвердить возврат?"
REFUND_SUCCESS = "Возврат успешно оформлен!"
REFUND_FAIL = "Ошибка при возврате!"

NOTIFICATION_SENT = "Уведомление отправлено."

BARISTA_HISTORY = "Последние действия:"
BARISTA_HISTORY_EMPTY = "История пуста."

# АДМИНКА
ADMIN_LOGIN_PROMPT = "Вход в админ-панель."
ADMIN_LOGIN_FAIL = "Неверный логин или пароль."
ADMIN_DASHBOARD = "Добро пожаловать в панель администратора!"
ADMIN_USER_MANAGEMENT = "Управление пользователями."
ADMIN_ANALYTICS = "Аналитика по системе."
ADMIN_FEEDBACKS = "Отзывы клиентов."
ADMIN_IDEAS = "Предложения клиентов."
ADMIN_ORDERS = "История заказов."
ADMIN_GIFTS = "История подарков."
ADMIN_NOTIFICATIONS = "Уведомления."
