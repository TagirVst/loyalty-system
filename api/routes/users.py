from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from slowapi import Limiter
from slowapi.util import get_remote_address
from common.schemas import UserOut, UserCreate
from common import crud
from common.models import User
from api.deps import get_session

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

@router.post("/", response_model=UserOut)
@limiter.limit("5/minute")
async def register_user(request: Request, user: UserCreate, session: AsyncSession = Depends(get_session)):
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
