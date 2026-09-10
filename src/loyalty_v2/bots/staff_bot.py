from __future__ import annotations

from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from loyalty_v2.application.auth_service import Permission, StaffAuthService
from loyalty_v2.application.client_service import ClientService
from loyalty_v2.application.order_service import IdentificationService, OrderService
from loyalty_v2.application.principal import PrincipalService
from loyalty_v2.application.refund_service import RefundService
from loyalty_v2.application.services import DomainError
from loyalty_v2.db.auth_models import StaffTerminal
from loyalty_v2.db.category_models import SaleCategory
from loyalty_v2.db.order_models import OrderDraft


class StaffFlow(StatesGroup):
    pin = State()
    amount = State()
    categories = State()
    points = State()
    code = State()
    rewards = State()
    confirm = State()
    cancel_reason = State()


class StaffBot:
    def __init__(self, *, bot: Bot, sessions: async_sessionmaker[AsyncSession], organization_id: UUID) -> None:
        self.bot, self.sessions, self.organization_id = bot, sessions, organization_id
        self.router = Router(name="staff-v2")
        self.auth = StaffAuthService()
        self.principals = PrincipalService()
        self.orders = OrderService()
        self.identification = IdentificationService()
        self.clients = ClientService()
        self.refunds = RefundService()
        self._routes()

    def dispatcher(self) -> Dispatcher:
        dp = Dispatcher(); dp.include_router(self.router); return dp

    @staticmethod
    def main_keyboard() -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Новая продажа")],[KeyboardButton(text="Выйти")]], resize_keyboard=True)

    async def _terminal(self, session: AsyncSession, chat_id: int) -> StaffTerminal | None:
        return await session.scalar(select(StaffTerminal).where(StaffTerminal.organization_id == self.organization_id, StaffTerminal.telegram_chat_id == chat_id, StaffTerminal.is_active.is_(True)))

    async def _principal(self, session: AsyncSession, state: FSMContext):
        data = await state.get_data(); raw = data.get("staff_session_id")
        if not raw: return None
        try: return await self.principals.staff(session, staff_session_id=UUID(raw))
        except (DomainError, ValueError): return None

    @staticmethod
    def _category_keyboard(items: list[tuple[str,str,str]], counts: dict[str,int]) -> InlineKeyboardMarkup:
        rows=[]
        for category_id,code,name in items:
            count=counts.get(code,0)
            rows.append([
                InlineKeyboardButton(text="−",callback_data=f"cm:{category_id}"),
                InlineKeyboardButton(text=f"{name}: {count}"[:40],callback_data="noop"),
                InlineKeyboardButton(text="+",callback_data=f"cp:{category_id}"),
            ])
        rows.append([InlineKeyboardButton(text="Готово",callback_data="categories_done")])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def _routes(self) -> None:
        @self.router.message(CommandStart())
        async def start(message: Message, state: FSMContext) -> None:
            async with self.sessions() as session: terminal = await self._terminal(session, message.chat.id)
            if not terminal:
                await state.clear(); await message.answer("Этот Telegram-чат не зарегистрирован как кассовый терминал.", reply_markup=ReplyKeyboardRemove()); return
            await state.set_state(StaffFlow.pin); await state.update_data(terminal_id=str(terminal.id)); await message.answer("Введите ваш 6-значный PIN.", reply_markup=ReplyKeyboardRemove())

        @self.router.message(StaffFlow.pin)
        async def pin(message: Message, state: FSMContext) -> None:
            data=await state.get_data(); terminal_id=UUID(data["terminal_id"])
            async with self.sessions() as session:
                async with session.begin(): attempt=await self.auth.authenticate_attempt(session,organization_id=self.organization_id,terminal_id=terminal_id,pin=(message.text or "").strip())
            if attempt.error: await message.answer("Неверный PIN или вход временно заблокирован."); return
            auth_session=attempt.auth_session; assert auth_session is not None
            await state.set_state(None); await state.update_data(staff_session_id=str(auth_session.id)); await message.answer("Вход выполнен.",reply_markup=self.main_keyboard())

        @self.router.message(F.text == "Новая продажа")
        async def new_sale(message: Message, state: FSMContext) -> None:
            async with self.sessions() as session: principal=await self._principal(session,state)
            if not principal: await message.answer("Сессия завершена. Выполните /start."); return
            await state.set_state(StaffFlow.amount); await message.answer("Введите сумму заказа в рублях.",reply_markup=ReplyKeyboardRemove())

        @self.router.message(StaffFlow.amount)
        async def amount(message: Message, state: FSMContext) -> None:
            try:
                value=Decimal((message.text or "").replace(",",".")); minor=int(value*100)
                if minor<=0 or value.as_tuple().exponent < -2: raise InvalidOperation
            except (InvalidOperation,ValueError): await message.answer("Введите корректную сумму, например 450 или 450,50."); return
            async with self.sessions() as session:
                categories=(await session.scalars(select(SaleCategory).where(SaleCategory.organization_id==self.organization_id,SaleCategory.is_active.is_(True)).order_by(SaleCategory.name.asc()))).all()
            await state.update_data(gross_amount_minor=minor)
            if categories:
                items=[(str(x.id),x.code,x.name) for x in categories]; await state.update_data(category_items=items,category_counts={}); await state.set_state(StaffFlow.categories)
                await message.answer("Укажите количество позиций по категориям. Если категория не нужна — оставьте 0.",reply_markup=self._category_keyboard(items,{})); return
            await state.update_data(category_counts={}); await state.set_state(StaffFlow.points); await message.answer("Сколько баллов списать? Введите 0, если не списывать.")

        @self.router.callback_query(StaffFlow.categories, F.data == "noop")
        async def noop(callback: CallbackQuery) -> None: await callback.answer()

        @self.router.callback_query(StaffFlow.categories, F.data.startswith("cp:"))
        async def category_plus(callback: CallbackQuery, state: FSMContext) -> None:
            data=await state.get_data(); items=data.get("category_items",[]); target=callback.data[3:]; code=next((c for i,c,_ in items if i==target),None)
            if code is None: await callback.answer(); return
            counts=dict(data.get("category_counts",{})); counts[code]=counts.get(code,0)+1; await state.update_data(category_counts=counts)
            await callback.message.edit_reply_markup(reply_markup=self._category_keyboard(items,counts)); await callback.answer()

        @self.router.callback_query(StaffFlow.categories, F.data.startswith("cm:"))
        async def category_minus(callback: CallbackQuery, state: FSMContext) -> None:
            data=await state.get_data(); items=data.get("category_items",[]); target=callback.data[3:]; code=next((c for i,c,_ in items if i==target),None)
            if code is None: await callback.answer(); return
            counts=dict(data.get("category_counts",{})); counts[code]=max(0,counts.get(code,0)-1)
            if counts[code]==0: counts.pop(code,None)
            await state.update_data(category_counts=counts); await callback.message.edit_reply_markup(reply_markup=self._category_keyboard(items,counts)); await callback.answer()

        @self.router.callback_query(StaffFlow.categories, F.data == "categories_done")
        async def categories_done(callback: CallbackQuery, state: FSMContext) -> None:
            await state.set_state(StaffFlow.points); await callback.message.edit_reply_markup(reply_markup=None); await callback.message.answer("Сколько баллов списать? Введите 0, если не списывать."); await callback.answer()

        @self.router.message(StaffFlow.points)
        async def points(message: Message, state: FSMContext) -> None:
            try:
                requested=int((message.text or "").strip())
                if requested<0: raise ValueError
            except ValueError: await message.answer("Введите целое число баллов, например 0 или 150."); return
            data=await state.get_data()
            async with self.sessions.begin() as session:
                principal=await self._principal(session,state)
                if not principal: await message.answer("Сессия завершена. Выполните /start."); return
                principal.require(Permission.SALE_CREATE)
                draft=await self.orders.create_draft(session,organization_id=principal.organization_id,location_id=principal.location_id,gross_amount_minor=data["gross_amount_minor"],requested_points=requested,category_counts=data.get("category_counts",{})); draft_id=draft.id
            await state.update_data(draft_id=str(draft_id)); await state.set_state(StaffFlow.code); await message.answer("Введите 5-значный код клиента.")

        @self.router.message(StaffFlow.code)
        async def identify(message: Message, state: FSMContext) -> None:
            code=(message.text or "").strip()
            if len(code)!=5 or not code.isdigit(): await message.answer("Код должен состоять из 5 цифр."); return
            data=await state.get_data(); draft_id=UUID(data["draft_id"])
            try:
                async with self.sessions.begin() as session:
                    principal=await self._principal(session,state)
                    if not principal: raise DomainError("Session ended")
                    draft=await self.identification.attach_to_draft(session,organization_id=principal.organization_id,draft_id=draft_id,code=code)
                    if draft.location_id!=principal.location_id: raise DomainError("Wrong location")
                    rewards=await self.clients.rewards(session,organization_id=principal.organization_id,customer_id=draft.customer_id); reward_data=[(str(r.id),d.name) for r,d in rewards]
            except DomainError as exc: await message.answer(f"Не удалось применить код: {exc}"); return
            await state.update_data(available_rewards=reward_data,selected_rewards=[]); await state.set_state(StaffFlow.rewards); await message.answer("Клиент найден. Выберите награды или сразу рассчитайте.",reply_markup=self._reward_keyboard(reward_data,set()))

        @self.router.callback_query(StaffFlow.rewards, F.data.startswith("rw:"))
        async def toggle_reward(callback: CallbackQuery, state: FSMContext) -> None:
            reward_id=callback.data[3:]; data=await state.get_data(); selected=set(data.get("selected_rewards",[])); selected.remove(reward_id) if reward_id in selected else selected.add(reward_id); await state.update_data(selected_rewards=list(selected)); await callback.message.edit_reply_markup(reply_markup=self._reward_keyboard(data.get("available_rewards",[]),selected)); await callback.answer()

        @self.router.callback_query(StaffFlow.rewards, F.data == "calc")
        async def calculate(callback: CallbackQuery, state: FSMContext) -> None:
            data=await state.get_data(); draft_id=UUID(data["draft_id"]); selected=data.get("selected_rewards",[])
            try:
                async with self.sessions.begin() as session:
                    principal=await self._principal(session,state)
                    if not principal: raise DomainError("Session ended")
                    draft=await session.scalar(select(OrderDraft).where(OrderDraft.id==draft_id,OrderDraft.organization_id==principal.organization_id,OrderDraft.location_id==principal.location_id).with_for_update())
                    if not draft: raise DomainError("Draft unavailable")
                    draft.selected_reward_ids=selected; draft.version+=1; result=await self.orders.quote(session,organization_id=principal.organization_id,draft_id=draft.id); quote=result.quote
            except DomainError as exc: await callback.answer(); await callback.message.answer(f"Не удалось рассчитать: {exc}"); return
            await state.update_data(quote_id=str(quote.id)); await state.set_state(StaffFlow.confirm); await callback.message.edit_reply_markup(reply_markup=None); await callback.message.answer(self._quote_text(quote),reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Подтвердить продажу",callback_data="confirm_sale")],[InlineKeyboardButton(text="Отмена",callback_data="abort_sale")]])); await callback.answer()

        @self.router.callback_query(StaffFlow.confirm, F.data == "confirm_sale")
        async def confirm_sale(callback: CallbackQuery, state: FSMContext) -> None:
            data=await state.get_data(); draft_id,quote_id=UUID(data["draft_id"]),UUID(data["quote_id"]); key=f"staff-bot:{uuid4()}"
            try:
                async with self.sessions.begin() as session:
                    principal=await self._principal(session,state)
                    if not principal: raise DomainError("Session ended")
                    principal.require(Permission.SALE_CONFIRM); order=await self.orders.confirm(session,organization_id=principal.organization_id,draft_id=draft_id,quote_id=quote_id,idempotency_key=key,actor_staff_id=principal.staff_id)
            except DomainError as exc: await callback.answer(); await callback.message.answer(f"Не удалось подтвердить: {exc}"); return
            await state.set_state(None); await state.update_data(last_order_id=str(order.id)); kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отменить эту продажу",callback_data=f"cancel:{order.id}")]]); await callback.message.edit_reply_markup(reply_markup=None); await callback.message.answer(f"Продажа проведена.\nОплачено: {order.paid_amount_minor/100:.2f} ₽\nНачислено баллов: {order.points_earned}",reply_markup=kb); await callback.answer()

        @self.router.callback_query(F.data.startswith("cancel:"))
        async def cancel_request(callback: CallbackQuery, state: FSMContext) -> None: await state.update_data(cancel_order_id=callback.data[7:]); await state.set_state(StaffFlow.cancel_reason); await callback.message.answer("Укажите причину отмены продажи."); await callback.answer()

        @self.router.message(StaffFlow.cancel_reason)
        async def cancel_reason(message: Message, state: FSMContext) -> None:
            reason=(message.text or "").strip()
            if not reason: await message.answer("Причина обязательна."); return
            data=await state.get_data(); order_id=UUID(data["cancel_order_id"]); key=f"staff-cancel:{uuid4()}"
            try:
                async with self.sessions.begin() as session:
                    principal=await self._principal(session,state)
                    if not principal: raise DomainError("Session ended")
                    principal.require(Permission.SALE_CANCEL_OWN)
                    from loyalty_v2.db.order_models import Order
                    order=await session.get(Order,order_id)
                    if not order or order.actor_staff_id!=principal.staff_id or order.location_id!=principal.location_id or order.organization_id!=principal.organization_id: raise DomainError("This order cannot be cancelled by current staff")
                    refund=await self.refunds.confirm(session,organization_id=principal.organization_id,order_id=order_id,actor_staff_id=principal.staff_id,reason=reason,idempotency_key=key,cashier_cancel=True)
            except DomainError as exc: await message.answer(f"Не удалось отменить: {exc}"); return
            await state.set_state(None); await message.answer(f"Продажа отменена. Возвращено баллов: {refund.restored_points}.",reply_markup=self.main_keyboard())

        @self.router.callback_query(StaffFlow.confirm, F.data == "abort_sale")
        async def abort(callback: CallbackQuery, state: FSMContext) -> None: await state.set_state(None); await callback.message.edit_reply_markup(reply_markup=None); await callback.message.answer("Продажа не проведена.",reply_markup=self.main_keyboard()); await callback.answer()

        @self.router.message(F.text == "Выйти")
        async def logout(message: Message, state: FSMContext) -> None:
            data=await state.get_data(); raw=data.get("staff_session_id")
            if raw:
                try:
                    async with self.sessions.begin() as session: await self.auth.logout(session,UUID(raw))
                except DomainError: pass
            await state.clear(); await message.answer("Смена завершена. Для входа используйте /start.",reply_markup=ReplyKeyboardRemove())

    @staticmethod
    def _reward_keyboard(items:list[tuple[str,str]],selected:set[str])->InlineKeyboardMarkup:
        rows=[]
        for reward_id,name in items:
            mark="✓ " if reward_id in selected else ""; rows.append([InlineKeyboardButton(text=f"{mark}{name}"[:60],callback_data=f"rw:{reward_id}")])
        rows.append([InlineKeyboardButton(text="Рассчитать",callback_data="calc")]); return InlineKeyboardMarkup(inline_keyboard=rows)

    @staticmethod
    def _quote_text(q)->str:
        return f"К оплате: {q.paid_amount_minor/100:.2f} ₽\nСписать баллов: {q.redeemed_points}\nНачислить баллов: {q.points_to_earn}"
