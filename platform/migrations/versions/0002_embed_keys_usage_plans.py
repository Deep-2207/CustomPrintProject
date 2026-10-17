"""embed keys, usage, plans

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-17 12:24:04.201815
"""
from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('api_keys',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=8), nullable=False),
    sa.Column('prefix', sa.String(length=16), nullable=False),
    sa.Column('key_value', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('key_value')
    )
    with op.batch_alter_table('api_keys', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_api_keys_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('usage_daily',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('day', sa.Date(), nullable=False),
    sa.Column('kind', sa.String(length=10), nullable=False),
    sa.Column('count', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'day', 'kind', name='uq_usage_day_kind')
    )
    with op.batch_alter_table('usage_daily', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_usage_daily_tenant_id'), ['tenant_id'], unique=False)

    with op.batch_alter_table('designs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source', sa.String(length=10), server_default='share', nullable=False))
        batch_op.add_column(sa.Column('ref', sa.String(length=80), server_default='', nullable=False))
        batch_op.add_column(sa.Column('billable', sa.Boolean(), server_default=sa.true(), nullable=False))

    with op.batch_alter_table('tenants', schema=None) as batch_op:
        batch_op.add_column(sa.Column('allowed_domains', sa.JSON(), server_default=sa.text("'[]'"), nullable=False))
        batch_op.add_column(sa.Column('plan', sa.String(length=16), server_default='pilot', nullable=False))
        batch_op.add_column(sa.Column('setup_fee', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('setup_fee_paid', sa.Boolean(), server_default=sa.false(), nullable=False))



def downgrade() -> None:
    with op.batch_alter_table('tenants', schema=None) as batch_op:
        batch_op.drop_column('setup_fee_paid')
        batch_op.drop_column('setup_fee')
        batch_op.drop_column('plan')
        batch_op.drop_column('allowed_domains')

    with op.batch_alter_table('designs', schema=None) as batch_op:
        batch_op.drop_column('billable')
        batch_op.drop_column('ref')
        batch_op.drop_column('source')

    with op.batch_alter_table('usage_daily', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_usage_daily_tenant_id'))

    op.drop_table('usage_daily')
    with op.batch_alter_table('api_keys', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_api_keys_tenant_id'))

    op.drop_table('api_keys')
