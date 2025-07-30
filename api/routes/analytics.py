from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from api.deps import get_session
from common.models import Order, Gift

router = APIRouter()

@router.get("/summary")
async def analytics_summary(session: AsyncSession = Depends(get_session)):
    total_orders = (await session.execute(select(func.count(Order.id)))).scalar()
    total_gifts = (await session.execute(select(func.count(Gift.id)))).scalar()
    total_drinks = (await session.execute(select(func.sum(Order.drinks_count)))).scalar()
    total_sandwiches = (await session.execute(select(func.sum(Order.sandwiches_count)))).scalar()
    return {
        "total_orders": total_orders,
        "total_gifts": total_gifts,
        "total_drinks": total_drinks or 0,
        "total_sandwiches": total_sandwiches or 0,
    }
