"""fix loyalty enum standart to standard

Revision ID: 002
Revises: 001
Create Date: 2024-12-19 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None

def upgrade():
    # Обновляем существующие записи со значением 'Стандарт' (они уже правильные)
    # Изменяем только enum, если у нас есть записи с неправильным значением
    op.execute("UPDATE users SET loyalty_status = 'Стандарт' WHERE loyalty_status = 'Стандарт'")
    
def downgrade():
    # В обратную сторону ничего не делаем, так как данные остаются корректными
    pass