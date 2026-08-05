"""portal_text_colors_and_favicon

Revision ID: b9a004db60a1
Revises: 94e56e26f2d8
Create Date: 2026-08-05 13:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b9a004db60a1'
down_revision = '94e56e26f2d8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('portals', schema=None) as batch_op:
        batch_op.add_column(sa.Column('favicon_path', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('heading_text_color', sa.String(length=7), nullable=True, server_default='#111111'))
        batch_op.add_column(sa.Column('body_text_color', sa.String(length=7), nullable=True, server_default='#374151'))
        batch_op.add_column(sa.Column('button_text_color', sa.String(length=7), nullable=True, server_default='#FFFFFF'))


def downgrade():
    with op.batch_alter_table('portals', schema=None) as batch_op:
        batch_op.drop_column('button_text_color')
        batch_op.drop_column('body_text_color')
        batch_op.drop_column('heading_text_color')
        batch_op.drop_column('favicon_path')
