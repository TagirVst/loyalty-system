"""Track cashier actor. Revision ID: 0008_order_actor Revises: 0007_refunds"""
from alembic import op
import sqlalchemy as sa
revision="0008_order_actor"; down_revision="0007_refunds"; branch_labels=None; depends_on=None
def upgrade():
    op.add_column("orders_v2",sa.Column("actor_staff_id",sa.Uuid(),nullable=True)); op.create_foreign_key("fk_orders_v2_actor_staff","orders_v2","staff",["actor_staff_id"],["id"],ondelete="RESTRICT"); op.create_index("ix_orders_v2_actor_staff_id","orders_v2",["actor_staff_id"])
def downgrade():
    op.drop_index("ix_orders_v2_actor_staff_id",table_name="orders_v2"); op.drop_constraint("fk_orders_v2_actor_staff","orders_v2",type_="foreignkey"); op.drop_column("orders_v2","actor_staff_id")
