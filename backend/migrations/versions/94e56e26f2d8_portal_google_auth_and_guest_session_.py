"""portal google_auth_enabled and guest_session auth_method

Revision ID: 94e56e26f2d8
Revises: e7ae0038f6bd
Create Date: 2026-08-03 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '94e56e26f2d8'
down_revision = 'e7ae0038f6bd'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('portals', schema=None) as batch_op:
        batch_op.add_column(sa.Column('google_auth_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))

    with op.batch_alter_table('guest_sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('auth_method', sa.String(length=20), nullable=False, server_default='form'))


def downgrade():
    with op.batch_alter_table('guest_sessions', schema=None) as batch_op:
        batch_op.drop_column('auth_method')

    with op.batch_alter_table('portals', schema=None) as batch_op:
        batch_op.drop_column('google_auth_enabled')
