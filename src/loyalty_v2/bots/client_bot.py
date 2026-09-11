from __future__ import annotations

from datetime import date
from uuid import UUID

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from loyalty_v2.application.customer_auth_service import CustomerAuthService
from loyalty_v2.application.customer_portal_service import CustomerPortalService
from loyalty_v2.application.services import CustomerAlreadyExists, CustomerNotFound, CustomerService


class Registration(StatesGroup):
    name = State()
    phone = State()
    birth_date = State()


class FeedbackFlow(StatesGroup):
    rating = State()
    comment = State()


class ClientBot:
    def __init__(self, *, bot: Bot, sessions: async_sessionmaker[AsyncSession], organization_id: UUID) -> None:
        self.bot, self.sessions, self.organization_id = bot, sessions, organization_id
        self.router = Router(name="client-v2")
        self.customers = CustomerService()
        self.auth = CustomerAuthService()
        self.portal = CustomerPortalService()
        self._routes()

    def dispatcher(self) -> Dispatcher:
        dp = Dispatcher(); dp.include_router(self.router); return dp

    @staticmethod
    def _external_session_key(message: Message) -> str:
        return f"telegram:{message.chat.id}:{message.from_user.id}"

    async def _session_id(self, session: AsyncSession, message: Message) -> UUID | None:
        try:
            item = await self.auth.open_session(session, organization_id=self.organization_id, provider="telegram", external_subject=str(message.from_user.id), external_session_key=self._external_session_key(message))
        except CustomerNotFound:
            return None
        return item.id

    @staticmethod
    def main_keyboard() -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="Получить код")],
            [KeyboardButton(text="Мои награды"), KeyboardButton(text="История")],
            [KeyboardButton(text="Профиль"), KeyboardButton(text="Оставить отзыв")],
            [KeyboardButton(text="Уведомления")],
        ], resize_keyboard=True)

    def _routes(self) -> None:
        @self.router.message(CommandStart())
        async def start(message: Message, state: FSMContext) -> None:
            await state.clear()
            async with self.sessions.begin() as session:
                customer_session_id = await self._session_id(session, message)
                if customer_session_id:
                    home = await self.portal.home(session, customer_session_id=customer_session_id)
                    await message.answer(self._home_text(home), reply_markup=self.main_keyboard()); return
            await state.set_state(Registration.name); await message.answer("Регистрация\n\nКак вас зовут?", reply_markup=ReplyKeyboardRemove())

        @self.router.message(Registration.name)
        async def registration_name(message: Message, state: FSMContext) -> None:
            name=(message.text or "").strip()
            if not name: await message.answer("Введите имя."); return
            await state.update_data(name=name); await state.set_state(Registration.phone)
            kb=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Поделиться номером",request_contact=True)]],resize_keyboard=True,one_time_keyboard=True)
            await message.answer("Поделитесь номером телефона.",reply_markup=kb)

        @self.router.message(Registration.phone, F.contact)
        async def registration_phone(message: Message, state: FSMContext) -> None:
            if message.contact.user_id != message.from_user.id: await message.answer("Нужно отправить свой номер кнопкой ниже."); return
            await state.update_data(phone=message.contact.phone_number); await state.set_state(Registration.birth_date)
            await message.answer("Введите дату рождения в формате ДД.ММ.ГГГГ.",reply_markup=ReplyKeyboardRemove())

        @self.router.message(Registration.birth_date)
        async def registration_birth(message: Message, state: FSMContext) -> None:
            try: day,month,year=map(int,(message.text or "").split(".")); birth=date(year,month,day)
            except (ValueError,TypeError): await message.answer("Не получилось распознать дату. Формат: ДД.ММ.ГГГГ."); return
            data=await state.get_data()
            try:
                async with self.sessions.begin() as session:
                    await self.customers.register(session,organization_id=self.organization_id,provider="telegram",external_subject=str(message.from_user.id),first_name=data["name"],phone=data["phone"],birth_date=birth)
                    customer_session_id = await self._session_id(session, message)
                    home = await self.portal.home(session, customer_session_id=customer_session_id)
            except CustomerAlreadyExists: await message.answer("Этот номер или Telegram уже зарегистрирован."); return
            await state.clear(); await message.answer(self._home_text(home),reply_markup=self.main_keyboard())

        @self.router.message(F.text == "Получить код")
        async def code(message: Message) -> None:
            async with self.sessions.begin() as session:
                customer_session_id=await self._session_id(session,message)
                if not customer_session_id: await message.answer("Сначала пройдите регистрацию: /start"); return
                item=await self.portal.identification_code(session,customer_session_id=customer_session_id)
            await message.answer(f"Ваш код: {item.code}\n\nПокажите его сотруднику. Код действует 90 секунд.")

        @self.router.message(F.text == "Мои награды")
        async def rewards(message: Message) -> None:
            async with self.sessions.begin() as session:
                customer_session_id=await self._session_id(session,message)
                if not customer_session_id: await message.answer("Сначала пройдите регистрацию: /start"); return
                items=await self.portal.rewards(session,customer_session_id=customer_session_id)
            if not items: await message.answer("Активных наград сейчас нет."); return
            lines=["Ваши награды:"]
            for reward,definition in items:
                name=(reward.definition_snapshot or {}).get("name") or definition.name
                expiry=reward.valid_until.strftime("%d.%m.%Y") if reward.valid_until else "без срока"; lines.append(f"• {name} ×{reward.quantity_remaining} — до {expiry}")
            await message.answer("\n".join(lines))

        @self.router.message(F.text == "История")
        async def history(message: Message) -> None:
            async with self.sessions.begin() as session:
                customer_session_id=await self._session_id(session,message)
                if not customer_session_id: await message.answer("Сначала пройдите регистрацию: /start"); return
                items=await self.portal.history(session,customer_session_id=customer_session_id,limit=10)
            if not items: await message.answer("История пока пустая."); return
            lines=["Последние операции:"]
            for item in items:
                sign="+" if item.delta>0 else ""; debt=f" · долг {item.debt_after}" if getattr(item,"debt_after",0) else ""; lines.append(f"• {item.created_at.strftime('%d.%m.%Y')}  {sign}{item.delta} → {item.balance_after}{debt}")
            await message.answer("\n".join(lines))

        @self.router.message(F.text == "Профиль")
        async def profile(message: Message) -> None:
            async with self.sessions.begin() as session:
                customer_session_id=await self._session_id(session,message)
                if not customer_session_id: await message.answer("Сначала пройдите регистрацию: /start"); return
                home=await self.portal.home(session,customer_session_id=customer_session_id)
            c=home.customer; await message.answer(f"{c.first_name}\nТелефон: {c.phone}\nДата рождения: {c.birth_date.strftime('%d.%m.%Y')}\nУровень: {home.tier_name}")

        @self.router.message(F.text == "Оставить отзыв")
        async def feedback_start(message: Message, state: FSMContext) -> None:
            async with self.sessions.begin() as session:
                if not await self._session_id(session,message): await message.answer("Сначала пройдите регистрацию: /start"); return
            await state.set_state(FeedbackFlow.rating)
            await message.answer("Оцените посещение от 1 до 5.", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=str(x)) for x in range(1,6)]],resize_keyboard=True,one_time_keyboard=True))

        @self.router.message(FeedbackFlow.rating)
        async def feedback_rating(message: Message, state: FSMContext) -> None:
            try: rating=int((message.text or "").strip())
            except ValueError: rating=0
            if rating not in range(1,6): await message.answer("Выберите оценку от 1 до 5."); return
            await state.update_data(rating=rating); await state.set_state(FeedbackFlow.comment)
            await message.answer("Напишите комментарий или нажмите «Пропустить».",reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Пропустить")]],resize_keyboard=True,one_time_keyboard=True))

        @self.router.message(FeedbackFlow.comment)
        async def feedback_comment(message: Message, state: FSMContext) -> None:
            data=await state.get_data(); comment=None if (message.text or "").strip()=="Пропустить" else (message.text or "").strip()[:5000]
            async with self.sessions.begin() as session:
                customer_session_id=await self._session_id(session,message)
                if not customer_session_id: await state.clear(); await message.answer("Сессия недоступна. Нажмите /start"); return
                item=await self.portal.submit_feedback(session,customer_session_id=customer_session_id,rating=int(data["rating"]),comment=comment)
            await state.clear()
            text="Спасибо, отзыв отправлен."
            if item.external_review_offered: text += "\nСпасибо за высокую оценку."
            await message.answer(text,reply_markup=self.main_keyboard())

        @self.router.message(F.text == "Уведомления")
        async def notification_settings(message: Message) -> None:
            async with self.sessions.begin() as session:
                customer_session_id=await self._session_id(session,message)
                if not customer_session_id: await message.answer("Сначала пройдите регистрацию: /start"); return
                prefs=await self.portal.notification_preferences(session,customer_session_id=customer_session_id)
            status="включены" if prefs.marketing_enabled else "выключены"
            action="Отключить акции" if prefs.marketing_enabled else "Включить акции"
            await message.answer(f"Уведомления об акциях: {status}.\nСервисные уведомления остаются включёнными.",reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=action)],[KeyboardButton(text="Назад")]],resize_keyboard=True,one_time_keyboard=True))

        @self.router.message(F.text.in_({"Включить акции","Отключить акции"}))
        async def notification_toggle(message: Message) -> None:
            enabled=message.text=="Включить акции"
            async with self.sessions.begin() as session:
                customer_session_id=await self._session_id(session,message)
                if not customer_session_id: await message.answer("Сначала пройдите регистрацию: /start"); return
                await self.portal.set_marketing_notifications(session,customer_session_id=customer_session_id,enabled=enabled)
            await message.answer("Уведомления об акциях включены." if enabled else "Уведомления об акциях выключены.",reply_markup=self.main_keyboard())

        @self.router.message(F.text == "Назад")
        async def back(message: Message, state: FSMContext) -> None:
            await state.clear(); await message.answer("Главное меню",reply_markup=self.main_keyboard())

    @staticmethod
    def _home_text(home) -> str:
        cashback=home.cashback_basis_points/100; lines=[f"{home.customer.first_name}, ваша карта",f"Баллы: {home.balance}",f"Уровень: {home.tier_name}",f"Кэшбэк: {cashback:g}%"]
        if getattr(home,"debt",0): lines.append(f"Долг по баллам: {home.debt}")
        if home.next_tier_name and home.next_tier_minimum_spend_minor is not None:
            left=max(0,home.next_tier_minimum_spend_minor-home.qualification_spend_minor)/100; lines.append(f"До {home.next_tier_name}: {left:,.0f} ₽".replace(","," "))
        return "\n".join(lines)
