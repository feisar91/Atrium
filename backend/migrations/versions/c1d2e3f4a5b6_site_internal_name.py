"""site internal_name

The internal site name UniFi puts in the hotspot redirect
(/guest/s/<internal_name>/). For self-hosted controllers it's the same value
as unifi_site_id; for Site Manager (cloud) controllers unifi_site_id is the
Site Manager siteId instead, so dispatch needs this to resolve the site.
Cloud rows are filled in by the next controller sync.

Revision ID: c1d2e3f4a5b6
Revises: b9a004db60a1
Create Date: 2026-11-12 08:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1d2e3f4a5b6'
down_revision = 'b9a004db60a1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('unifi_sites', schema=None) as batch_op:
        batch_op.add_column(sa.Column('internal_name', sa.String(length=100), nullable=True))
        batch_op.create_index('ix_unifi_sites_internal_name', ['internal_name'], unique=False)

    op.execute(
        """
        UPDATE unifi_sites SET internal_name = unifi_site_id
        WHERE controller_id IN (
            SELECT id FROM unifi_controllers WHERE controller_type <> 'cloud'
        )
        """
    )


def downgrade():
    with op.batch_alter_table('unifi_sites', schema=None) as batch_op:
        batch_op.drop_index('ix_unifi_sites_internal_name')
        batch_op.drop_column('internal_name')
