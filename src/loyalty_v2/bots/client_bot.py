from __future__ import annotations

from datetime import date
from uuid import UUID

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from loyalty_v2.application.client_service import ClientService
from loyalty_v2.application.order_service import IdentificationService
from loyalty_v2.application.services import CustomerAlreadyExists, CustomerService


class Registration(StatesGroup):
    name = State()
    phone = State()
    birth_date = State()


class ClientBot:
    def __init__(self, *, bot: Bot, sessions: async_sessionmaker[AsyncSession], organization_id: UUID) -> None:
        self.bot, self.sessions, self.organization_id = bot, sessions, organization_id
        self.router = Router(name="client-v2")
        self.customers, self.client, self.identification = CustomerService(), ClientService(), IdentificationService()
        self._routes()

    def dispatcher(self) -> Dispatcher:
        dp = Dispatcher(); dp.include_router(self.router); return dp

    async def _customer_id(self, session: AsyncSession, telegram_id: int) -> UUID | None:
        customer = await self.customers.find_by_identity(session, organization_id=self.organization_id, provider="telegram", external_subject=str(telegram_id))
        return customer.id if customer else None

    @staticmethod
    def main_keyboard() -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Получить код")],[KeyboardButton(text="Мои награды"),KeyboardButton(text="История")],[KeyboardButton(text="Профиль")]], resize_keyboard=True)

    def _routes(self) -> None:
        @self.router.message(CommandStart())
        async def start(message: Message, state: FSMContext) -> None:
            async with self.sessions() as session:
                customer_id = await self._customer_id(session, message.from_user.id)
                if customer_id:
                    home = await self.client.home(session, organization_id=self.organization_id, customer_id=customer_id)
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
                    result=await self.customers.register(session,organization_id=self.organization_id,provider="telegram",external_subject=str(message.from_user.id),first_name=data["name"],phone=data["phone"],birth_date=birth)
                    customer_id=result.customer.id
            except CustomerAlreadyExists: await message.answer("Этот номер или Telegram уже зарегистрирован."); return
            await state.clear()
            async with self.sessions() as session: home=await self.client.home(session,organization_id=self.organization_id,customer_id=customer_id)
            await message.answer(self._home_text(home),reply_markup=self.main_keyboard())

        @self.router.message(F.text == "Получить код")
        async def code(message: Message) -> None:
            async with self.sessions.begin() as session:
                customer_id=await self._customer_id(session,message.from_user.id)
                if not customer_id: await message.answer("Сначала пройдите регистрацию: /start"); return
                item=await self.identification.generate(session,organization_id=self.organization_id,customer_id=customer_id)
            await message.answer(f"Ваш код: {item.code}\n\nПокажите его сотруднику. Код действует 90 секунд.")

        @self.router.message(F.text == "Мои награды")
        async def rewards(message: Message) -> None:
            async with self.sessions() as session:
                customer_id=await self._customer_id(session,message.from_user.id)
                if not customer_id: await message.answer("Сначала пройдите регистрацию: /start"); return
                items=await self.client.rewards(session,organization_id=self.organization_id,customer_id=customer_id)
            if not items: await message.answer("Активных наград сейчас нет."); return
            lines=["Ваши награды:"]
            for reward,definition in items:
                expiry=reward.valid_until.strftime("%d.%m.%Y") if reward.valid_until else "без срока"; lines.append(f"• {definition.name} ×{reward.quantity_remaining} — до {expiry}")
            await message.answer("\n".join(lines))

        @self.router.message(F.text == "История")
        async def history(message: Message) -> None:
            async with self.sessions() as session:
                customer_id=await self._customer_id(session,message.from_user.id)
                if not customer_id: await message.answer("Сначала пройдите регистрацию: /start"); return
                items=await self.client.history(session,organization_id=self.organization_id,customer_id=customer_id,limit=10)
            if not items: await message.answer("История пока пустая."); return
            lines=["Последние операции:"]
            for item in items:
                sign="+" if item.delta>0 else ""; lines.append(f"• {item.created_at.strftime('%d.%m.%Y')}  {sign}{item.delta} → {item.balance_after}")
            await message.answer("\n".join(lines))

        @self.router.message(F.text == "Профиль")
        async def profile(message: Message) -> None:
            async with self.sessions() as session:
                customer_id=await self._customer_id(session,message.from_user.id)
                if not customer_id: await message.answer("Сначала пройдите регистрацию: /start"); return
                home=await self.client.home(session,organization_id=self.organization_id,customer_id=customer_id)
            c=home.customer; await message.answer(f"{c.first_name}\nТелефон: {c.phone}\nДата рождения: {c.birth_date.strftime('%d.%m.%Y')}\nУровень: {home.tier_name}")

    @staticmethod
    def _home_text(home) -> str:
        cashback=home.cashback_basis_points/100; lines=[f"{home.customer.first_name}, ваша карта",f"Баллы: {home.balance}",f"Уровень: {home.tier_name}",f"Кэшбэк: {cashback:g}%"]
        if home.next_tier_name and home.next_tier_minimum_spend_minor is not None:
            left=max(0,home.next_tier_minimum_spend_minor-home.qualification_spend_minor)/100; lines.append(f"До {home.next_tier_name}: {left:,.0f} ₽".replace(","," "))
        return "\n".join(lines)
