from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import httpx
import logging
from common import buttons, messages
from barista_bot.config import API_BASE_URL

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()

# Универсальная функция для API вызовов с обработкой ошибок
async def safe_api_call(url: str, method: str = "GET", json_data: dict = None, params: dict = None):
    """Безопасный вызов API с обработкой ошибок"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if method.upper() == "GET":
                response = await client.get(url, params=params)
            elif method.upper() == "POST":
                response = await client.post(url, json=json_data, params=params)
            else:
                logger.error(f"Неподдерживаемый HTTP метод: {method}")
                return None, 500
            
            return response.json() if response.status_code == 200 else None, response.status_code
    except httpx.TimeoutException:
        logger.error(f"Timeout при обращении к {url}")
        return None, 408
    except httpx.RequestError as e:
        logger.error(f"Ошибка запроса к {url}: {e}")
        return None, 500
    except Exception as e:
        logger.error(f"Неожиданная ошибка при обращении к {url}: {e}")
        return None, 500

class OrderState(StatesGroup):
    waiting_for_code = State()
    confirm_client = State()
    waiting_for_receipt = State()
    waiting_for_sum = State()
    waiting_for_drinks = State()
    waiting_for_sandwiches = State()
    waiting_for_points = State()
    confirm_order = State()

def kb_barista():
    return types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton(text=buttons.BTN_ORDER)],
        [types.KeyboardButton(text=buttons.BTN_CREATE_NOTIFICATION)],
        [types.KeyboardButton(text=buttons.BTN_GIFT)],
        [types.KeyboardButton(text=buttons.BTN_WRITEOFF_GIFT)],
        [types.KeyboardButton(text=buttons.BTN_HISTORY)]
    ], resize_keyboard=True)

@router.message(CommandStart())
async def start(msg: types.Message, state: FSMContext):
    await msg.answer(messages.BARISTA_WELCOME, reply_markup=kb_barista())

@router.message(F.text == buttons.BTN_ORDER)
async def start_order(msg: types.Message, state: FSMContext):
    await msg.answer(messages.ORDER_CODE_INPUT)
    await state.set_state(OrderState.waiting_for_code)

@router.message(OrderState.waiting_for_code)
async def order_code(msg: types.Message, state: FSMContext):
    code = msg.text.strip()
    
    # Используем код
    result, status_code = await safe_api_call(f"{API_BASE_URL}/codes/use", "POST", params={"code_value": code})
    if status_code != 200 or not result:
        error_msg = messages.CODE_INVALID
        if status_code == 408:
            error_msg = "Превышено время ожидания. Проверьте подключение к интернету."
        elif status_code == 404:
            error_msg = "Код не найден или уже использован."
        
        await msg.answer(error_msg, reply_markup=kb_barista())
        await state.clear()
        return
    
    user_id = result["user_id"]
    
    # Получаем профиль клиента
    user_result, user_status = await safe_api_call(f"{API_BASE_URL}/users/{user_id}")
    if user_status != 200 or not user_result:
        await msg.answer("Ошибка при получении данных клиента. Попробуйте позже.", reply_markup=kb_barista())
        await state.clear()
        return
    
    await state.update_data(user_id=user_id, code_id=result["id"])
    await msg.answer(messages.ORDER_CLIENT_FOUND.format(first_name=user_result['first_name'], last_name=user_result['last_name']))
    await msg.answer(messages.ORDER_INPUT_RECEIPT)
    await state.set_state(OrderState.waiting_for_receipt)

@router.message(OrderState.waiting_for_receipt)
async def order_receipt(msg: types.Message, state: FSMContext):
    await state.update_data(receipt_number=msg.text.strip())
    await msg.answer(messages.ORDER_INPUT_SUM)
    await state.set_state(OrderState.waiting_for_sum)

@router.message(OrderState.waiting_for_sum)
async def order_sum(msg: types.Message, state: FSMContext):
    await state.update_data(total_sum=int(msg.text.strip()))
    await msg.answer(messages.ORDER_INPUT_DRINKS)
    await state.set_state(OrderState.waiting_for_drinks)

@router.message(OrderState.waiting_for_drinks)
async def order_drinks(msg: types.Message, state: FSMContext):
    await state.update_data(drinks_count=int(msg.text.strip()))
    await msg.answer(messages.ORDER_INPUT_SANDWICHES)
    await state.set_state(OrderState.waiting_for_sandwiches)

@router.message(OrderState.waiting_for_sandwiches)
async def order_sandwiches(msg: types.Message, state: FSMContext):
    await state.update_data(sandwiches_count=int(msg.text.strip()))
    kb = types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton(text=buttons.BTN_ORDER_POINTS), types.KeyboardButton(text=buttons.BTN_ORDER_ACCUMULATE)]
    ], resize_keyboard=True)
    await msg.answer(messages.ORDER_POINTS_OR_ACCUM, reply_markup=kb)
    await state.set_state(OrderState.waiting_for_points)

@router.message(OrderState.waiting_for_points, F.text == buttons.BTN_ORDER_POINTS)
async def use_points(msg: types.Message, state: FSMContext):
    await state.update_data(use_points=True)
    await msg.answer(messages.ORDER_CONFIRM, reply_markup=types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text=buttons.BTN_CONFIRM)]], resize_keyboard=True))
    await state.set_state(OrderState.confirm_order)

@router.message(OrderState.waiting_for_points, F.text == buttons.BTN_ORDER_ACCUMULATE)
async def accumulate_points(msg: types.Message, state: FSMContext):
    await state.update_data(use_points=False)
    await msg.answer(messages.ORDER_CONFIRM, reply_markup=types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text=buttons.BTN_CONFIRM)]], resize_keyboard=True))
    await state.set_state(OrderState.confirm_order)

@router.message(OrderState.confirm_order, F.text == buttons.BTN_CONFIRM)
async def confirm_order(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    order_json = {
        "user_id": data["user_id"],
        "barista_id": msg.from_user.id,
        "code_id": data["code_id"],
        "receipt_number": data["receipt_number"],
        "total_sum": data["total_sum"],
        "drinks_count": data["drinks_count"],
        "sandwiches_count": data["sandwiches_count"],
        "use_points": data["use_points"],
        "used_points_amount": 0  # TODO: получить из профиля пользователя если требуется списание
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{API_BASE_URL}/orders/", json=order_json)
    if r.status_code == 200:
        await msg.answer(messages.ORDER_SUCCESS, reply_markup=kb_barista())
    else:
        await msg.answer(messages.ORDER_FAIL, reply_markup=kb_barista())
    await state.clear()

class GiftState(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_gift_type = State()
    waiting_for_gift_amount = State()
    confirm_gift = State()

class WriteOffState(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_gift_selection = State()
    confirm_writeoff = State()

class NotificationState(StatesGroup):
    waiting_for_text = State()
    waiting_for_target = State()
    waiting_for_user_id = State()
    confirm_notification = State()

# ПОДАРКИ
@router.message(F.text == buttons.BTN_GIFT)
async def start_gift(msg: types.Message, state: FSMContext):
    await msg.answer("Введите Telegram ID пользователя для выдачи подарка:")
    await state.set_state(GiftState.waiting_for_user_id)

@router.message(GiftState.waiting_for_user_id)
async def gift_user_id(msg: types.Message, state: FSMContext):
    user_id = msg.text.strip()
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_BASE_URL}/users/{user_id}")
        if r.status_code == 200:
            user = r.json()
            await state.update_data(target_user=user)
            kb = types.ReplyKeyboardMarkup(keyboard=[
                [types.KeyboardButton(text="Напиток")],
                [types.KeyboardButton(text="Сэндвич")],
                [types.KeyboardButton(text="Назад")]
            ], resize_keyboard=True)
            await msg.answer(f"Пользователь найден: {user['first_name']} {user['last_name']}\nВыберите тип подарка:", reply_markup=kb)
            await state.set_state(GiftState.waiting_for_gift_type)
        else:
            await msg.answer("Пользователь не найден. Попробуйте еще раз или введите 'Назад':")

@router.message(GiftState.waiting_for_gift_type)
async def gift_type(msg: types.Message, state: FSMContext):
    if msg.text == "Назад":
        await msg.answer("Отменено", reply_markup=kb_barista())
        await state.clear()
        return
    
    if msg.text in ["Напиток", "Сэндвич"]:
        gift_type = "drink" if msg.text == "Напиток" else "sandwich"
        await state.update_data(gift_type=gift_type)
        await msg.answer("Введите количество (по умолчанию 1):")
        await state.set_state(GiftState.waiting_for_gift_amount)
    else:
        await msg.answer("Выберите 'Напиток' или 'Сэндвич':")

@router.message(GiftState.waiting_for_gift_amount)
async def gift_amount(msg: types.Message, state: FSMContext):
    try:
        amount = int(msg.text.strip()) if msg.text.strip().isdigit() else 1
        if amount <= 0:
            amount = 1
        await state.update_data(amount=amount)
        
        data = await state.get_data()
        user = data["target_user"]
        gift_type_ru = "напитков" if data["gift_type"] == "drink" else "сэндвичей"
        
        confirmation_text = f"""Подтвердите выдачу подарка:
Пользователь: {user['first_name']} {user['last_name']}
Тип: {gift_type_ru}
Количество: {amount}"""
        
        kb = types.ReplyKeyboardMarkup(keyboard=[
            [types.KeyboardButton(text=buttons.BTN_CONFIRM)],
            [types.KeyboardButton(text="Отмена")]
        ], resize_keyboard=True)
        
        await msg.answer(confirmation_text, reply_markup=kb)
        await state.set_state(GiftState.confirm_gift)
    except ValueError:
        await msg.answer("Введите корректное число или оставьте пустым для 1:")

@router.message(GiftState.confirm_gift)
async def confirm_gift(msg: types.Message, state: FSMContext):
    if msg.text == "Отмена":
        await msg.answer("Отменено", reply_markup=kb_barista())
        await state.clear()
        return
    
    if msg.text == buttons.BTN_CONFIRM:
        data = await state.get_data()
        gift_data = {
            "user_id": data["target_user"]["id"],
            "type": data["gift_type"],
            "amount": data["amount"],
            "created_by": msg.from_user.id  # ID бариста
        }
        
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{API_BASE_URL}/gifts/", json=gift_data)
            if r.status_code == 200:
                gift_type_ru = "напитков" if data["gift_type"] == "drink" else "сэндвичей"
                await msg.answer(f"✅ Подарок выдан: {data['amount']} {gift_type_ru} для {data['target_user']['first_name']}", reply_markup=kb_barista())
            else:
                await msg.answer("❌ Ошибка при выдаче подарка", reply_markup=kb_barista())
    
    await state.clear()

# СПИСАНИЕ ПОДАРКОВ
@router.message(F.text == buttons.BTN_WRITEOFF_GIFT)
async def start_writeoff(msg: types.Message, state: FSMContext):
    await msg.answer("Введите Telegram ID пользователя для списания подарка:")
    await state.set_state(WriteOffState.waiting_for_user_id)

@router.message(WriteOffState.waiting_for_user_id)
async def writeoff_user_id(msg: types.Message, state: FSMContext):
    user_id = msg.text.strip()
    async with httpx.AsyncClient() as client:
        # Получаем пользователя
        user_r = await client.get(f"{API_BASE_URL}/users/{user_id}")
        if user_r.status_code == 200:
            user = user_r.json()
            await state.update_data(target_user=user)
            
            # Получаем активные подарки пользователя
            gifts_r = await client.get(f"{API_BASE_URL}/gifts/user/{user['id']}")
            if gifts_r.status_code == 200:
                gifts = gifts_r.json()
                active_gifts = [g for g in gifts if not g.get('is_written_off', True)]
                
                if active_gifts:
                    await state.update_data(available_gifts=active_gifts)
                    gifts_text = "Доступные подарки:\n"
                    buttons_list = []
                    
                    for i, gift in enumerate(active_gifts[:10]):  # Ограничиваем 10 подарками
                        gift_type_ru = "напиток" if gift['type'] == "drink" else "сэндвич"
                        gifts_text += f"{i+1}. {gift_type_ru} (x{gift['amount']})\n"
                        buttons_list.append([types.KeyboardButton(text=str(i+1))])
                    
                    buttons_list.append([types.KeyboardButton(text="Назад")])
                    kb = types.ReplyKeyboardMarkup(keyboard=buttons_list, resize_keyboard=True)
                    
                    await msg.answer(f"Пользователь: {user['first_name']} {user['last_name']}\n\n{gifts_text}\nВыберите номер подарка для списания:", reply_markup=kb)
                    await state.set_state(WriteOffState.waiting_for_gift_selection)
                else:
                    await msg.answer("У пользователя нет активных подарков", reply_markup=kb_barista())
                    await state.clear()
            else:
                await msg.answer("Ошибка при получении подарков", reply_markup=kb_barista())
                await state.clear()
        else:
            await msg.answer("Пользователь не найден. Попробуйте еще раз:")

@router.message(WriteOffState.waiting_for_gift_selection)
async def writeoff_select_gift(msg: types.Message, state: FSMContext):
    if msg.text == "Назад":
        await msg.answer("Отменено", reply_markup=kb_barista())
        await state.clear()
        return
    
    try:
        gift_index = int(msg.text) - 1
        data = await state.get_data()
        available_gifts = data["available_gifts"]
        
        if 0 <= gift_index < len(available_gifts):
            selected_gift = available_gifts[gift_index]
            await state.update_data(selected_gift=selected_gift)
            
            gift_type_ru = "напиток" if selected_gift['type'] == "drink" else "сэндвич"
            confirmation_text = f"Списать подарок: {gift_type_ru} (x{selected_gift['amount']}) у пользователя {data['target_user']['first_name']}?"
            
            kb = types.ReplyKeyboardMarkup(keyboard=[
                [types.KeyboardButton(text=buttons.BTN_CONFIRM)],
                [types.KeyboardButton(text="Отмена")]
            ], resize_keyboard=True)
            
            await msg.answer(confirmation_text, reply_markup=kb)
            await state.set_state(WriteOffState.confirm_writeoff)
        else:
            await msg.answer("Неверный номер. Попробуйте еще раз:")
    except ValueError:
        await msg.answer("Введите номер подарка:")

@router.message(WriteOffState.confirm_writeoff)
async def confirm_writeoff(msg: types.Message, state: FSMContext):
    if msg.text == "Отмена":
        await msg.answer("Отменено", reply_markup=kb_barista())
        await state.clear()
        return
    
    if msg.text == buttons.BTN_CONFIRM:
        data = await state.get_data()
        gift_id = data["selected_gift"]["id"]
        
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{API_BASE_URL}/gifts/{gift_id}/writeoff")
            if r.status_code == 200:
                gift_type_ru = "напиток" if data["selected_gift"]['type'] == "drink" else "сэндвич"
                await msg.answer(f"✅ Подарок списан: {gift_type_ru} у {data['target_user']['first_name']}", reply_markup=kb_barista())
            else:
                await msg.answer("❌ Ошибка при списании подарка", reply_markup=kb_barista())
    
    await state.clear()

# УВЕДОМЛЕНИЯ
@router.message(F.text == buttons.BTN_CREATE_NOTIFICATION)
async def start_notification(msg: types.Message, state: FSMContext):
    await msg.answer("Введите текст уведомления:")
    await state.set_state(NotificationState.waiting_for_text)

@router.message(NotificationState.waiting_for_text)
async def notification_text(msg: types.Message, state: FSMContext):
    await state.update_data(notification_text=msg.text)
    
    kb = types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton(text=buttons.BTN_SEND_NOTIFICATION_ALL)],
        [types.KeyboardButton(text=buttons.BTN_SEND_NOTIFICATION_ONE)],
        [types.KeyboardButton(text="Отмена")]
    ], resize_keyboard=True)
    
    await msg.answer("Кому отправить уведомление?", reply_markup=kb)
    await state.set_state(NotificationState.waiting_for_target)

@router.message(NotificationState.waiting_for_target)
async def notification_target(msg: types.Message, state: FSMContext):
    if msg.text == "Отмена":
        await msg.answer("Отменено", reply_markup=kb_barista())
        await state.clear()
        return
    
    if msg.text == buttons.BTN_SEND_NOTIFICATION_ALL:
        await state.update_data(target_type="all")
        await confirm_notification(msg, state)
    elif msg.text == buttons.BTN_SEND_NOTIFICATION_ONE:
        await state.update_data(target_type="one")
        await msg.answer("Введите Telegram ID пользователя:")
        await state.set_state(NotificationState.waiting_for_user_id)

@router.message(NotificationState.waiting_for_user_id)
async def notification_user_id(msg: types.Message, state: FSMContext):
    user_id = msg.text.strip()
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_BASE_URL}/users/{user_id}")
        if r.status_code == 200:
            user = r.json()
            await state.update_data(target_user=user)
            await confirm_notification(msg, state)
        else:
            await msg.answer("Пользователь не найден. Попробуйте еще раз:")

async def confirm_notification(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    target_text = "всем пользователям" if data["target_type"] == "all" else f"пользователю {data.get('target_user', {}).get('first_name', 'ID')}"
    
    confirmation_text = f"""Отправить уведомление {target_text}?

Текст: {data['notification_text']}"""
    
    kb = types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton(text=buttons.BTN_SEND)],
        [types.KeyboardButton(text="Отмена")]
    ], resize_keyboard=True)
    
    await msg.answer(confirmation_text, reply_markup=kb)
    await state.set_state(NotificationState.confirm_notification)

@router.message(NotificationState.confirm_notification)
async def send_notification(msg: types.Message, state: FSMContext):
    if msg.text == "Отмена":
        await msg.answer("Отменено", reply_markup=kb_barista())
        await state.clear()
        return
    
    if msg.text == buttons.BTN_SEND:
        data = await state.get_data()
        notification_data = {
            "text": data["notification_text"],
            "sent_by": msg.from_user.id
        }
        
        if data["target_type"] == "one":
            notification_data["user_id"] = data["target_user"]["id"]
        
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{API_BASE_URL}/notifications/", json=notification_data)
            if r.status_code == 200:
                target_text = "всем пользователям" if data["target_type"] == "all" else "пользователю"
                await msg.answer(f"✅ Уведомление отправлено {target_text}", reply_markup=kb_barista())
            else:
                await msg.answer("❌ Ошибка при отправке уведомления", reply_markup=kb_barista())
    
    await state.clear()

# ИСТОРИЯ ОПЕРАЦИЙ
@router.message(F.text == buttons.BTN_HISTORY)
async def show_history(msg: types.Message, state: FSMContext):
    async with httpx.AsyncClient() as client:
        # Получаем последние заказы
        orders_r = await client.get(f"{API_BASE_URL}/orders/recent", params={"limit": 10})
        if orders_r.status_code == 200:
            orders = orders_r.json()
            if orders:
                history_text = "📋 Последние 10 заказов:\n\n"
                for order in orders:
                    history_text += f"🔹 Заказ #{order.get('receipt_number', 'N/A')}\n"
                    history_text += f"   Сумма: {order.get('total_sum', 0)} руб.\n"
                    history_text += f"   Напитки: {order.get('drinks_count', 0)}, Сэндвичи: {order.get('sandwiches_count', 0)}\n"
                    history_text += f"   Дата: {order.get('date_created', '')[:16]}\n\n"
                
                await msg.answer(history_text, reply_markup=kb_barista())
            else:
                await msg.answer("История заказов пуста", reply_markup=kb_barista())
        else:
            await msg.answer("Ошибка при получении истории", reply_markup=kb_barista())
