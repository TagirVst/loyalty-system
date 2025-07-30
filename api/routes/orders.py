from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from common.schemas import OrderCreate, OrderOut
from common import crud
from api.deps import get_session

router = APIRouter()

@router.post("/", response_model=OrderOut)
async def create_order(order: OrderCreate, session: AsyncSession = Depends(get_session)):
    # Валидация входных данных
    if order.total_sum <= 0:
        raise HTTPException(400, "Сумма заказа должна быть больше 0")
    
    if order.drinks_count < 0 or order.sandwiches_count < 0:
        raise HTTPException(400, "Количество товаров не может быть отрицательным")
    
    if order.drinks_count == 0 and order.sandwiches_count == 0:
        raise HTTPException(400, "Заказ должен содержать хотя бы один товар")
    
    if order.use_points and order.used_points_amount <= 0:
        raise HTTPException(400, "При списании баллов количество должно быть больше 0")
    
    if order.used_points_amount < 0:
        raise HTTPException(400, "Количество используемых баллов не может быть отрицательным")
    
    # Проверяем существование пользователя
    user = await crud.get_user_by_id(session, order.user_id)
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    
    # Проверяем достаточность баллов для списания
    if order.use_points and user.points < order.used_points_amount:
        raise HTTPException(400, f"Недостаточно баллов. Доступно: {user.points}, требуется: {order.used_points_amount}")
    
    # Создаем заказ
    order_obj = await crud.create_order(session, **order.model_dump())
    
    # Обновляем статистику пользователя
    await crud.update_user_stats_after_order(session, order.user_id, order.drinks_count, order.sandwiches_count, order.total_sum, order.use_points, order.used_points_amount)
    
    return OrderOut.model_validate(order_obj)

@router.get("/user/{user_id}", response_model=List[OrderOut])
async def get_user_orders(user_id: int, session: AsyncSession = Depends(get_session), limit: int = 10, offset: int = 0):
    orders = await crud.get_orders_by_user(session, user_id, limit, offset)
    return [OrderOut.model_validate(o) for o in orders]

@router.get("/", response_model=List[OrderOut])
async def list_all_orders(session: AsyncSession = Depends(get_session), limit: int = 100, offset: int = 0):
    """Получить все заказы (для админки)"""
    orders = await crud.get_all_orders(session, limit, offset)
    return [OrderOut.model_validate(o) for o in orders]

@router.get("/recent", response_model=List[OrderOut])
async def get_recent_orders(session: AsyncSession = Depends(get_session), limit: int = 10):
    """Получить последние заказы"""
    orders = await crud.get_recent_orders(session, limit)
    return [OrderOut.model_validate(o) for o in orders]
