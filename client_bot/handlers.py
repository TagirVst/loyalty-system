from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import ReplyKeyboardBuilder
import httpx
import logging
from common import buttons, messages
from client_bot.config import API_BASE_URL

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

class RegisterState(StatesGroup):
    waiting_for_phone = State()
    waiting_for_first_name = State()
    waiting_for_last_name = State()
    waiting_for_birthdate = State()
    confirm = State()

def kb_start():
    return types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text=buttons.BTN_START)]], resize_keyboard=True)

def kb_main():
    kb = [
        [types.KeyboardButton(text=buttons.BTN_PROFILE)],
        [types.KeyboardButton(text=buttons.BTN_GEN_CODE)],
        [types.KeyboardButton(text=buttons.BTN_FEEDBACK)]
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@router.message(CommandStart())
async def start(msg: types.Message, state: FSMContext):
    await msg.answer(messages.WELCOME_MSG, reply_markup=kb_start())

@router.message(F.text == buttons.BTN_START)
async def register(msg: types.Message, state: FSMContext):
    user_data, status_code = await safe_api_call(f"{API_BASE_URL}/users/{str(msg.from_user.id)}")
    if status_code == 200 and user_data:
        await msg.answer(messages.REGISTRATION_SUCCESS, reply_markup=kb_main())
        await state.clear()
        return
    elif status_code != 404:  # Если не 404 (пользователь не найден), значит другая ошибка
        await msg.answer("Произошла ошибка при проверке регистрации. Попробуйте позже.", reply_markup=kb_start())
        return
    kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="Отправить номер", request_contact=True)]], resize_keyboard=True
    )
    await msg.answer(messages.REGISTER_PHONE, reply_markup=kb)
    await state.set_state(RegisterState.waiting_for_phone)

@router.message(RegisterState.waiting_for_phone, F.contact)
async def get_phone(msg: types.Message, state: FSMContext):
    await state.update_data(phone=msg.contact.phone_number)
    await msg.answer(messages.REGISTER_FIRSTNAME, reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(RegisterState.waiting_for_first_name)

@router.message(RegisterState.waiting_for_first_name)
async def get_firstname(msg: types.Message, state: FSMContext):
    await state.update_data(first_name=msg.text)
    await msg.answer(messages.REGISTER_LASTNAME)
    await state.set_state(RegisterState.waiting_for_last_name)

@router.message(RegisterState.waiting_for_last_name)
async def get_lastname(msg: types.Message, state: FSMContext):
    await state.update_data(last_name=msg.text)
    await msg.answer(messages.REGISTER_BIRTHDATE)
    await state.set_state(RegisterState.waiting_for_birthdate)

@router.message(RegisterState.waiting_for_birthdate)
async def register_birthdate(msg: types.Message, state: FSMContext):
    try:
        # Улучшенная валидация даты
        date_parts = msg.text.strip().split(".")
        if len(date_parts) != 3:
            raise ValueError("Invalid format")
        
        d, m, y = map(int, date_parts)
        
        # Проверяем валидность даты
        from datetime import date
        birth_date = date(y, m, d)
        
        # Проверяем разумные границы возраста (от 10 до 100 лет)
        from datetime import date as today_date
        today = today_date.today()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        
        if age < 10 or age > 100:
            await msg.answer("Пожалуйста, введите корректную дату рождения (возраст от 10 до 100 лет)")
            return
        
        await state.update_data(birth_date=birth_date.strftime("%Y-%m-%d"))
    except (ValueError, TypeError):
        await msg.answer("Неверный формат даты. Введите как ДД.ММ.ГГГГ (например: 15.03.1990)")
        return
    
    data = await state.get_data()
    await msg.answer(f"<b>Проверьте данные:</b>\nИмя: {data['first_name']}\nФамилия: {data['last_name']}\nТелефон: {data['phone']}\nДата рождения: {msg.text}\n\nНажмите 'Подтвердить'.", reply_markup=types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text=buttons.BTN_CONFIRM)]], resize_keyboard=True))
    await state.set_state(RegisterState.confirm)

@router.message(RegisterState.confirm, F.text == buttons.BTN_CONFIRM)
async def register_confirm(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    user_data = {
        "telegram_id": str(msg.from_user.id),
        "phone": data.get("phone"),
        "first_name": data.get("first_name"),
        "last_name": data.get("last_name"),
        "birth_date": data.get("birth_date"),
    }
    
    result, status_code = await safe_api_call(f"{API_BASE_URL}/users/", "POST", user_data)
    if status_code == 200 and result:
        await msg.answer(messages.REGISTRATION_SUCCESS, reply_markup=kb_main())
        await state.clear()
    else:
        error_msg = "Ошибка регистрации. Попробуйте еще раз."
        if status_code == 400:
            error_msg = "Пользователь уже зарегистрирован."
        elif status_code == 408:
            error_msg = "Превышено время ожидания. Проверьте подключение к интернету."
        await msg.answer(error_msg, reply_markup=kb_start())
        await state.clear()

@router.message(F.text == buttons.BTN_PROFILE)
async def show_profile(msg: types.Message, state: FSMContext):
    user_data, status_code = await safe_api_call(f"{API_BASE_URL}/users/{str(msg.from_user.id)}")
    if status_code == 200 and user_data:
        await msg.answer(messages.PROFILE_TEMPLATE.format(**user_data), reply_markup=kb_main())
    elif status_code == 404:
        await msg.answer("Вы не зарегистрированы в системе. Пожалуйста, зарегистрируйтесь.", reply_markup=kb_start())
    else:
        await msg.answer("Ошибка при получении профиля. Попробуйте позже.", reply_markup=kb_main())

@router.message(F.text == buttons.BTN_GEN_CODE)
async def gen_code(msg: types.Message, state: FSMContext):
    result, status_code = await safe_api_call(f"{API_BASE_URL}/codes/generate", "POST", params={"user_id": str(msg.from_user.id)})
    
    if status_code == 200 and result:
        code = result["code"]
        await msg.answer(messages.CODE_GENERATED.format(code=code), reply_markup=types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text=buttons.BTN_GEN_NEW_CODE)], [types.KeyboardButton(text=buttons.BTN_BACK)]], resize_keyboard=True))
    elif status_code == 404:
        await msg.answer("Вы не зарегистрированы в системе. Пожалуйста, зарегистрируйтесь.", reply_markup=kb_start())
    elif status_code == 408:
        await msg.answer("Превышено время ожидания. Проверьте подключение к интернету.", reply_markup=kb_main())
    else:
        await msg.answer("Ошибка при генерации кода. Попробуйте позже.", reply_markup=kb_main())

@router.message(F.text == buttons.BTN_GEN_NEW_CODE)
async def gen_new_code(msg: types.Message, state: FSMContext):
    await gen_code(msg, state)

@router.message(F.text == buttons.BTN_BACK)
async def back_to_main(msg: types.Message, state: FSMContext):
    await msg.answer("Главное меню", reply_markup=kb_main())

@router.message(F.text == buttons.BTN_FEEDBACK)
async def feedback_menu(msg: types.Message, state: FSMContext):
    kb = types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton(text=buttons.BTN_LEAVE_FEEDBACK)],
        [types.KeyboardButton(text=buttons.BTN_LEAVE_IDEA)],
        [types.KeyboardButton(text=buttons.BTN_CONTACT_ADMIN)],
        [types.KeyboardButton(text=buttons.BTN_BACK)]
    ], resize_keyboard=True)
    await msg.answer(messages.FEEDBACK_MENU, reply_markup=kb)

class FeedbackState(StatesGroup):
    waiting_for_score = State()
    waiting_for_feedback_text = State()
    waiting_for_idea_text = State()
    waiting_for_admin_message = State()

@router.message(F.text == buttons.BTN_LEAVE_FEEDBACK)
async def start_feedback(msg: types.Message, state: FSMContext):
    score_buttons = []
    for i in range(1, 11):
        if i <= 5:
            score_buttons.append(types.KeyboardButton(text=str(i)))
        else:
            if len(score_buttons) == 5:
                score_buttons = [score_buttons]
                score_buttons.append([])
            score_buttons[-1].append(types.KeyboardButton(text=str(i)))
    
    if not isinstance(score_buttons[0], list):
        score_buttons = [score_buttons]
    
    score_buttons.append([types.KeyboardButton(text=buttons.BTN_BACK_FEEDBACK)])
    
    kb = types.ReplyKeyboardMarkup(keyboard=score_buttons, resize_keyboard=True)
    await msg.answer("Пожалуйста, оцените наш сервис от 1 до 10:", reply_markup=kb)
    await state.set_state(FeedbackState.waiting_for_score)

@router.message(FeedbackState.waiting_for_score)
async def get_feedback_score(msg: types.Message, state: FSMContext):
    if msg.text == buttons.BTN_BACK_FEEDBACK:
        await feedback_menu(msg, state)
        return
    
    try:
        score = int(msg.text)
        if 1 <= score <= 10:
            await state.update_data(score=score)
            if score >= 8:
                await msg.answer(messages.FEEDBACK_THANKS_POSITIVE, reply_markup=types.ReplyKeyboardMarkup(
                    keyboard=[[types.KeyboardButton(text=buttons.BTN_SEND)], [types.KeyboardButton(text=buttons.BTN_BACK_FEEDBACK)]], 
                    resize_keyboard=True))
                # Сразу отправляем положительный отзыв
                await send_feedback_to_api(msg, state, score, "Положительный отзыв")
            else:
                await msg.answer(messages.FEEDBACK_THANKS_NEGATIVE, reply_markup=types.ReplyKeyboardMarkup(
                    keyboard=[[types.KeyboardButton(text=buttons.BTN_BACK_FEEDBACK)]], resize_keyboard=True))
                await state.set_state(FeedbackState.waiting_for_feedback_text)
        else:
            await msg.answer("Пожалуйста, введите число от 1 до 10")
    except ValueError:
        await msg.answer("Пожалуйста, введите число от 1 до 10")

@router.message(FeedbackState.waiting_for_feedback_text)
async def get_feedback_text(msg: types.Message, state: FSMContext):
    if msg.text == buttons.BTN_BACK_FEEDBACK:
        await feedback_menu(msg, state)
        return
    
    data = await state.get_data()
    await send_feedback_to_api(msg, state, data['score'], msg.text)

async def send_feedback_to_api(msg: types.Message, state: FSMContext, score: int, text: str):
    # Сначала получим данные пользователя
    user_data, user_status = await safe_api_call(f"{API_BASE_URL}/users/{str(msg.from_user.id)}")
    if user_status == 200 and user_data:
        feedback_data = {
            "user_id": user_data["id"],
            "score": score,
            "text": text
        }
        result, status_code = await safe_api_call(f"{API_BASE_URL}/feedback/review", "POST", json_data=feedback_data)
        if status_code == 200:
            await msg.answer(messages.FEEDBACK_SENT, reply_markup=kb_main())
        elif status_code == 408:
            await msg.answer("Превышено время ожидания. Попробуйте позже.", reply_markup=kb_main())
        else:
            await msg.answer("Произошла ошибка при отправке отзыва", reply_markup=kb_main())
    elif user_status == 404:
        await msg.answer("Вы не зарегистрированы в системе.", reply_markup=kb_start())
    else:
        await msg.answer("Ошибка при получении данных пользователя. Попробуйте позже.", reply_markup=kb_main())
    await state.clear()

@router.message(F.text == buttons.BTN_LEAVE_IDEA)
async def start_idea(msg: types.Message, state: FSMContext):
    await msg.answer("Поделитесь своей идеей для улучшения нашего кафе:", 
                    reply_markup=types.ReplyKeyboardMarkup(
                        keyboard=[[types.KeyboardButton(text=buttons.BTN_BACK_FEEDBACK)]], 
                        resize_keyboard=True))
    await state.set_state(FeedbackState.waiting_for_idea_text)

@router.message(FeedbackState.waiting_for_idea_text)
async def get_idea_text(msg: types.Message, state: FSMContext):
    if msg.text == buttons.BTN_BACK_FEEDBACK:
        await feedback_menu(msg, state)
        return
    
    # Получаем данные пользователя
    user_data, user_status = await safe_api_call(f"{API_BASE_URL}/users/{str(msg.from_user.id)}")
    if user_status == 200 and user_data:
        idea_data = {
            "user_id": user_data["id"],
            "text": msg.text
        }
        result, status_code = await safe_api_call(f"{API_BASE_URL}/feedback/idea", "POST", json_data=idea_data)
        if status_code == 200:
            await msg.answer(messages.IDEA_SENT, reply_markup=kb_main())
        elif status_code == 408:
            await msg.answer("Превышено время ожидания. Попробуйте позже.", reply_markup=kb_main())
        else:
            await msg.answer("Произошла ошибка при отправке идеи", reply_markup=kb_main())
    elif user_status == 404:
        await msg.answer("Вы не зарегистрированы в системе.", reply_markup=kb_start())
    else:
        await msg.answer("Ошибка при получении данных пользователя. Попробуйте позже.", reply_markup=kb_main())
    await state.clear()

@router.message(F.text == buttons.BTN_CONTACT_ADMIN)
async def start_admin_contact(msg: types.Message, state: FSMContext):
    await msg.answer("Напишите ваше сообщение для руководства:", 
                    reply_markup=types.ReplyKeyboardMarkup(
                        keyboard=[[types.KeyboardButton(text=buttons.BTN_BACK_FEEDBACK)]], 
                        resize_keyboard=True))
    await state.set_state(FeedbackState.waiting_for_admin_message)

@router.message(FeedbackState.waiting_for_admin_message)
async def get_admin_message(msg: types.Message, state: FSMContext):
    if msg.text == buttons.BTN_BACK_FEEDBACK:
        await feedback_menu(msg, state)
        return
    
    # Получаем информацию о пользователе
    user_data, user_status = await safe_api_call(f"{API_BASE_URL}/users/{str(msg.from_user.id)}")
    if user_status == 200 and user_data:
        # Отправляем как идею с пометкой "Сообщение для руководства"
        idea_data = {
            "user_id": user_data["id"],
            "text": f"📞 Сообщение для руководства от {user_data['first_name']} {user_data['last_name']}:\n\n{msg.text}"
        }
        result, status_code = await safe_api_call(f"{API_BASE_URL}/feedback/idea", "POST", json_data=idea_data)
        if status_code == 200:
            await msg.answer("Ваше сообщение отправлено руководству!", reply_markup=kb_main())
        elif status_code == 408:
            await msg.answer("Превышено время ожидания. Попробуйте позже.", reply_markup=kb_main())
        else:
            await msg.answer("Произошла ошибка при отправке сообщения", reply_markup=kb_main())
    elif user_status == 404:
        await msg.answer("Вы не зарегистрированы в системе.", reply_markup=kb_start())
    else:
        await msg.answer("Ошибка при получении данных пользователя. Попробуйте позже.", reply_markup=kb_main())
    await state.clear()

# Обработчик для кнопки "Назад" в меню обратной связи
@router.message(F.text == buttons.BTN_BACK_FEEDBACK)
async def back_to_feedback_menu(msg: types.Message, state: FSMContext):
    await feedback_menu(msg, state)
