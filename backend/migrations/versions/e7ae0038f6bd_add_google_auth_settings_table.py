"""add google_auth_settings table

Revision ID: e7ae0038f6bd
Revises: ff4b91d0a83d
Create Date: 2026-08-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e7ae0038f6bd'
down_revision = 'ff4b91d0a83d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('google_auth_settings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('client_id', sa.String(length=255), nullable=True),
    sa.Column('client_secret_encrypted', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('google_auth_settings')
