from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, func
from datetime import datetime, timedelta, date
import secrets

from .models import (
    User, Barista, Code, Order, Gift, Feedback, Idea, Notification, BaristaAction, RoleEnum, LoyaltyLevelEnum
)

# USERS
async def create_user(session: AsyncSession, telegram_id: str, **kwargs):
    user = User(telegram_id=telegram_id, **kwargs)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

async def get_user_by_telegram(session: AsyncSession, telegram_id: str):
    q = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return q.scalar_one_or_none()

async def get_user_by_id(session: AsyncSession, user_id: int):
    q = await session.execute(select(User).where(User.id == user_id))
    return q.scalar_one_or_none()

async def update_user(session: AsyncSession, user_id: int, **kwargs):
    await session.execute(update(User).where(User.id == user_id).values(**kwargs))
    await session.commit()

async def update_user_stats_after_order(session: AsyncSession, user_id: int, drinks_count: int, sandwiches_count: int, total_sum: int, use_points: bool, used_points_amount: int):
    """Обновляем статистику пользователя после заказа"""
    # Дополнительные проверки на валидность данных
    if drinks_count < 0 or sandwiches_count < 0:
        raise ValueError("Количество товаров не может быть отрицательным")
    
    if total_sum <= 0:
        raise ValueError("Сумма заказа должна быть больше 0")
    
    if used_points_amount < 0:
        raise ValueError("Количество используемых баллов не может быть отрицательным")
    
    user = await get_user_by_id(session, user_id)
    if not user:
        raise ValueError("Пользователь не найден")
    
    # Проверяем достаточность баллов для списания
    if use_points and user.points < used_points_amount:
        raise ValueError(f"Недостаточно баллов. Доступно: {user.points}, требуется: {used_points_amount}")
    
    # Обновляем счетчики
    new_drinks_count = user.drinks_count + drinks_count
    new_sandwiches_count = user.sandwiches_count + sandwiches_count
    
    # Рассчитываем баллы (1 балл за каждые 100 руб, но только если не списываем баллы)
    points_earned = 0 if use_points else total_sum // 100
    
    # Списываем или начисляем баллы
    if use_points:
        new_points = max(0, user.points - used_points_amount)
    else:
        new_points = user.points + points_earned
    
    # Определяем новый уровень лояльности
    from .utils import get_loyalty_level
    new_level = get_loyalty_level(new_drinks_count)
    
    # Преобразуем строку уровня в enum
    level_mapping = {
        "Стандарт": LoyaltyLevelEnum.standard,
        "Серебро": LoyaltyLevelEnum.silver,
        "Золото": LoyaltyLevelEnum.gold,
        "Платина": LoyaltyLevelEnum.platinum,
    }
    new_loyalty_status = level_mapping.get(new_level, LoyaltyLevelEnum.standard)
    
    # Обновляем пользователя
    await update_user(session, user_id, 
                     drinks_count=new_drinks_count,
                     sandwiches_count=new_sandwiches_count,
                     points=new_points,
                     loyalty_status=new_loyalty_status)
    
    # Проверяем день рождения и выдаем подарок если нужно
    await check_and_give_birthday_gift(session, user_id)
    
    # Возвращаем информацию об изменениях для уведомлений
    level_upgraded = user.loyalty_status != new_loyalty_status
    birthday_gift = await check_and_give_birthday_gift(session, user_id)
    
    return {
        "points_earned": points_earned,
        "points_used": used_points_amount if use_points else 0,
        "new_points_total": new_points,
        "level_upgraded": level_upgraded,
        "new_level": new_level if level_upgraded else None,
        "birthday_gift": birthday_gift
    }

async def set_loyalty_level(session: AsyncSession, user_id: int, level: LoyaltyLevelEnum):
    await update_user(session, user_id, loyalty_status=level)

# BARISTAS
async def get_barista_by_telegram(session: AsyncSession, telegram_id: str):
    q = await session.execute(select(Barista).where(Barista.telegram_id == telegram_id))
    return q.scalar_one_or_none()

async def create_barista(session: AsyncSession, telegram_id: str, **kwargs):
    barista = Barista(telegram_id=telegram_id, **kwargs)
    session.add(barista)
    await session.commit()
    await session.refresh(barista)
    return barista

# CODES
async def generate_code(session: AsyncSession, user_id: int, validity_seconds: int = 90):
    # Генерируем уникальный 5-значный код, валиден 90 сек
    while True:
        code_value = "".join([str(secrets.randbelow(10)) for _ in range(5)])
        q = await session.execute(select(Code).where(Code.code == code_value, Code.is_used == False))
        if not q.scalar_one_or_none():
            break
    expires_at = datetime.utcnow() + timedelta(seconds=validity_seconds)
    code = Code(code=code_value, user_id=user_id, expires_at=expires_at)
    session.add(code)
    await session.commit()
    await session.refresh(code)
    return code

async def use_code(session: AsyncSession, code_value: str):
    q = await session.execute(select(Code).where(Code.code == code_value, Code.is_used == False))
    code = q.scalar_one_or_none()
    if not code:
        return None
    if code.expires_at < datetime.utcnow():
        return None
    code.is_used = True
    await session.commit()
    return code

# ORDERS
async def create_order(session: AsyncSession, **kwargs):
    order = Order(**kwargs)
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order

async def get_orders_by_user(session: AsyncSession, user_id: int, limit: int = 10, offset: int = 0):
    q = await session.execute(
        select(Order).where(Order.user_id == user_id).order_by(Order.date_created.desc()).offset(offset).limit(limit)
    )
    return q.scalars().all()

async def get_all_orders(session: AsyncSession, limit: int = 100, offset: int = 0):
    """Получить все заказы для админки"""
    q = await session.execute(
        select(Order).order_by(Order.date_created.desc()).offset(offset).limit(limit)
    )
    return q.scalars().all()

async def get_recent_orders(session: AsyncSession, limit: int = 10):
    """Получить последние заказы"""
    q = await session.execute(
        select(Order).order_by(Order.date_created.desc()).limit(limit)
    )
    return q.scalars().all()

# GIFTS
async def create_gift(session: AsyncSession, user_id: int, type_: str, amount: int, created_by: int = None):
    gift = Gift(user_id=user_id, type=type_, amount=amount, created_by=created_by)
    session.add(gift)
    await session.commit()
    await session.refresh(gift)
    return gift

async def write_off_gift(session: AsyncSession, gift_id: int):
    q = await session.execute(select(Gift).where(Gift.id == gift_id, Gift.is_written_off == False))
    gift = q.scalar_one_or_none()
    if not gift:
        return None
    gift.is_written_off = True
    await session.commit()
    return gift

async def get_gifts_by_user(session: AsyncSession, user_id: int, active_only: bool = True):
    """Получить подарки пользователя"""
    if active_only:
        q = await session.execute(
            select(Gift).where(Gift.user_id == user_id, Gift.is_written_off == False).order_by(Gift.date_created.desc())
        )
    else:
        q = await session.execute(
            select(Gift).where(Gift.user_id == user_id).order_by(Gift.date_created.desc())
        )
    return q.scalars().all()

async def get_all_gifts(session: AsyncSession, limit: int = 100, offset: int = 0):
    """Получить все подарки для админки"""
    q = await session.execute(
        select(Gift).order_by(Gift.date_created.desc()).offset(offset).limit(limit)
    )
    return q.scalars().all()

# FEEDBACK
async def create_feedback(session: AsyncSession, user_id: int, score: int, text: str = None):
    feedback = Feedback(user_id=user_id, score=score, text=text)
    session.add(feedback)
    await session.commit()
    await session.refresh(feedback)
    return feedback

async def get_feedbacks(session: AsyncSession, limit: int = 10, offset: int = 0):
    q = await session.execute(select(Feedback).order_by(Feedback.created_at.desc()).offset(offset).limit(limit))
    return q.scalars().all()

# IDEAS
async def create_idea(session: AsyncSession, user_id: int, text: str):
    idea = Idea(user_id=user_id, text=text)
    session.add(idea)
    await session.commit()
    await session.refresh(idea)
    return idea

async def get_ideas(session: AsyncSession, limit: int = 10, offset: int = 0):
    q = await session.execute(select(Idea).order_by(Idea.created_at.desc()).offset(offset).limit(limit))
    return q.scalars().all()

# NOTIFICATIONS
async def create_notification(session: AsyncSession, text: str, sent_by: int = None, user_id: int = None):
    notification = Notification(text=text, sent_by=sent_by, user_id=user_id)
    session.add(notification)
    await session.commit()
    await session.refresh(notification)
    return notification

async def get_notifications_for_user(session: AsyncSession, user_id: int, limit: int = 10, offset: int = 0):
    q = await session.execute(
        select(Notification).where(
            (Notification.user_id == user_id) | (Notification.user_id == None)
        ).order_by(Notification.date_sent.desc()).offset(offset).limit(limit)
    )
    return q.scalars().all()

# BARISTA ACTIONS
async def log_barista_action(session: AsyncSession, barista_id: int, action_type: str, details: str = None):
    action = BaristaAction(barista_id=barista_id, action_type=action_type, details=details)
    session.add(action)
    await session.commit()
    await session.refresh(action)
    return action

# BIRTHDAY GIFTS
async def check_and_give_birthday_gift(session: AsyncSession, user_id: int):
    """Проверяет день рождения пользователя и выдает подарок"""
    user = await get_user_by_id(session, user_id)
    if not user or not user.birth_date:
        return False
    
    from .utils import is_birthday_today
    if is_birthday_today(user.birth_date):
        # Проверяем, не выдавали ли уже подарок сегодня
        existing_gift = await session.execute(
            select(Gift).where(
                Gift.user_id == user_id,
                Gift.type == "birthday_drink",
                func.date(Gift.date_created) == date.today()
            )
        )
        if existing_gift.scalar_one_or_none():
            return False  # Подарок уже выдан сегодня
        
        # Выдаем подарок на день рождения
        birthday_gift = await create_gift(session, user_id, "birthday_drink", 1)
        
        # Обновляем счетчик подарочных напитков
        await update_user(session, user_id, gift_drinks=user.gift_drinks + 1)
        
        return True
    return False

# AUTOMATIC LOYALTY LEVEL UPDATE
async def check_and_update_loyalty_level(session: AsyncSession, user_id: int):
    """Проверяет и обновляет уровень лояльности пользователя"""
    user = await get_user_by_id(session, user_id)
    if not user:
        return False
    
    from .utils import get_loyalty_level
    new_level_str = get_loyalty_level(user.drinks_count)
    
    # Преобразуем строку в enum
    level_mapping = {
        "Стандарт": LoyaltyLevelEnum.standard,
        "Серебро": LoyaltyLevelEnum.silver,
        "Золото": LoyaltyLevelEnum.gold,
        "Платина": LoyaltyLevelEnum.platinum,
    }
    new_level = level_mapping.get(new_level_str, LoyaltyLevelEnum.standard)
    
    # Проверяем, изменился ли уровень
    if user.loyalty_status != new_level:
        await update_user(session, user_id, loyalty_status=new_level)
        return True, new_level_str
    
    return False, None
