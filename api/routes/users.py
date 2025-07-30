from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import re
from datetime import date, datetime
from slowapi import Limiter
from slowapi.util import get_remote_address
from common.schemas import UserOut, UserCreate
from common import crud
from common.models import User
from api.deps import get_session

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

def validate_phone(phone: str) -> bool:
    """Валидация номера телефона"""
    if not phone:
        return False
    # Простая проверка российского номера
    phone_pattern = re.compile(r'^(\+7|8)?[\s\-]?\(?[489]\d{2}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}$')
    return bool(phone_pattern.match(phone.replace(' ', '').replace('-', '')))

def validate_name(name: str) -> bool:
    """Валидация имени/фамилии"""
    if not name or len(name.strip()) < 2:
        return False
    # Проверяем, что содержит только буквы и пробелы
    return bool(re.match(r'^[а-яёА-ЯЁa-zA-Z\s]+$', name.strip()))

def validate_birth_date(birth_date: str) -> bool:
    """Валидация даты рождения"""
    try:
        birth_dt = datetime.strptime(birth_date, "%Y-%m-%d").date()
        today = date.today()
        age = today.year - birth_dt.year - ((today.month, today.day) < (birth_dt.month, birth_dt.day))
        return 10 <= age <= 100
    except (ValueError, TypeError):
        return False

@router.post("/", response_model=UserOut)
@limiter.limit("5/minute")
async def register_user(request: Request, user: UserCreate, session: AsyncSession = Depends(get_session)):
    # Валидация телефона
    if user.phone and not validate_phone(user.phone):
        raise HTTPException(400, "Неверный формат номера телефона")
    
    # Валидация имени
    if user.first_name and not validate_name(user.first_name):
        raise HTTPException(400, "Имя должно содержать только буквы и быть не короче 2 символов")
    
    # Валидация фамилии
    if user.last_name and not validate_name(user.last_name):
        raise HTTPException(400, "Фамилия должна содержать только буквы и быть не короче 2 символов")
    
    # Валидация даты рождения
    if user.birth_date and not validate_birth_date(user.birth_date):
        raise HTTPException(400, "Неверная дата рождения (возраст должен быть от 10 до 100 лет)")
    
    # Валидация telegram_id
    if not user.telegram_id or not user.telegram_id.strip():
        raise HTTPException(400, "Telegram ID обязателен")
    
    existed = await crud.get_user_by_telegram(session, user.telegram_id)
    if existed:
        raise HTTPException(400, "Пользователь уже зарегистрирован")
    user_obj = await crud.create_user(session, telegram_id=user.telegram_id, phone=user.phone,
        first_name=user.first_name, last_name=user.last_name, birth_date=user.birth_date)
    return UserOut.model_validate(user_obj)

@router.get("/", response_model=List[UserOut])
@limiter.limit("10/minute")
async def list_users(request: Request, session: AsyncSession = Depends(get_session), limit: int = 100, offset: int = 0):
    """Получить список всех пользователей (для админки)"""
    stmt = select(User).order_by(User.id.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    users = result.scalars().all()
    return [UserOut.model_validate(user) for user in users]

@router.get("/{telegram_id}", response_model=UserOut)
@limiter.limit("30/minute")
async def get_user(request: Request, telegram_id: str, session: AsyncSession = Depends(get_session)):
    user = await crud.get_user_by_telegram(session, telegram_id)
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    return UserOut.model_validate(user)
