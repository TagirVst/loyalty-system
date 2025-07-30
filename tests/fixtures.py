import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from common.models import Base, RoleEnum, LoyaltyLevelEnum
from common.crud import create_user, create_barista, create_gift, create_order

DATABASE_URL = "postgresql+asyncpg://loyalty_user:loyaltypass@db:5432/loyalty_db"
engine = create_async_engine(DATABASE_URL, echo=True)
Session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def main():
    async with Session() as session:
        await session.run_sync(Base.metadata.create_all)
        await create_user(session, telegram_id="10001", phone="+79990001122", first_name="Иван", last_name="Тестов", birth_date="2000-01-01")
        await create_barista(session, telegram_id="20001", first_name="Бариста", last_name="Главный", is_admin=True)
        await create_gift(session, user_id=1, type_="drink", amount=2, created_by=1)
        await create_order(session, user_id=1, barista_id=1, code_id=1, receipt_number="A-001", total_sum=250, drinks_count=2, sandwiches_count=1, use_points=False)

if __name__ == "__main__":
    asyncio.run(main())
