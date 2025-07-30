from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from common.schemas import GiftOut, GiftCreate
from common import crud
from api.deps import get_session

router = APIRouter()

@router.post("/", response_model=GiftOut)
async def create_gift(gift: GiftCreate, session: AsyncSession = Depends(get_session)):
    """Создать подарок для пользователя"""
    # Проверяем существование пользователя
    user = await crud.get_user_by_id(session, gift.user_id)
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    
    gift_obj = await crud.create_gift(session, **gift.model_dump())
    
    # Обновляем счетчики подарков у пользователя
    if gift.type == "drink":
        await crud.update_user(session, gift.user_id, gift_drinks=user.gift_drinks + gift.amount)
    elif gift.type == "sandwich":
        await crud.update_user(session, gift.user_id, gift_sandwiches=user.gift_sandwiches + gift.amount)
    
    return GiftOut.model_validate(gift_obj)

@router.get("/user/{user_id}", response_model=List[GiftOut])
async def get_user_gifts(user_id: int, session: AsyncSession = Depends(get_session), active_only: bool = True):
    """Получить подарки пользователя"""
    gifts = await crud.get_gifts_by_user(session, user_id, active_only)
    return [GiftOut.model_validate(g) for g in gifts]

@router.post("/{gift_id}/writeoff", response_model=GiftOut)
async def writeoff_gift(gift_id: int, session: AsyncSession = Depends(get_session)):
    """Списать подарок"""
    gift = await crud.write_off_gift(session, gift_id)
    if not gift:
        raise HTTPException(404, "Подарок не найден или уже списан")
    return GiftOut.model_validate(gift)

@router.get("/", response_model=List[GiftOut])
async def list_all_gifts(session: AsyncSession = Depends(get_session), limit: int = 100, offset: int = 0):
    """Получить все подарки (для админки)"""
    gifts = await crud.get_all_gifts(session, limit, offset)
    return [GiftOut.model_validate(g) for g in gifts]
