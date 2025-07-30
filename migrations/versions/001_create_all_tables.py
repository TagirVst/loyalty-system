"""create all tables

Revision ID: 001
Revises: 
Create Date: 2024-06-27 21:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg

revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telegram_id', sa.String(), nullable=False),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('first_name', sa.String(), nullable=True),
        sa.Column('last_name', sa.String(), nullable=True),
        sa.Column('birth_date', sa.Date(), nullable=True),
        sa.Column('loyalty_status', pg.ENUM('Стандарт', 'Серебро', 'Золото', 'Платина', name='loyaltylevelenum'), nullable=False, server_default='Стандарт'),
        sa.Column('points', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('drinks_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sandwiches_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('gift_drinks', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('gift_sandwiches', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column('role', pg.ENUM('client', 'barista', 'admin', name='roleenum'), nullable=False, server_default='client'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telegram_id')
    )

    op.create_table('baristas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telegram_id', sa.String(), nullable=False),
        sa.Column('first_name', sa.String(), nullable=True),
        sa.Column('last_name', sa.String(), nullable=True),
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telegram_id')
    )

    op.create_table('codes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('is_used', sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )

    op.create_table('orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('barista_id', sa.Integer(), sa.ForeignKey('baristas.id'), nullable=True),
        sa.Column('code_id', sa.Integer(), sa.ForeignKey('codes.id'), nullable=True),
        sa.Column('receipt_number', sa.String(), nullable=False),
        sa.Column('total_sum', sa.Integer(), nullable=False),
        sa.Column('drinks_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sandwiches_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('use_points', sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column('used_points_amount', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('date_created', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('gifts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('baristas.id'), nullable=True),
        sa.Column('date_created', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('is_written_off', sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('feedbacks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('score', sa.Integer(), nullable=True),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('ideas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('sent_by', sa.Integer(), sa.ForeignKey('baristas.id'), nullable=True),
        sa.Column('date_sent', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('barista_actions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('barista_id', sa.Integer(), sa.ForeignKey('baristas.id'), nullable=True),
        sa.Column('action_type', sa.String(), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('barista_actions')
    op.drop_table('notifications')
    op.drop_table('ideas')
    op.drop_table('feedbacks')
    op.drop_table('gifts')
    op.drop_table('orders')
    op.drop_table('codes')
    op.drop_table('baristas')
    op.drop_table('users')
    op.execute("DROP TYPE IF EXISTS loyaltylevelenum")
    op.execute("DROP TYPE IF EXISTS roleenum")
