"""global dns zone uniqueness

Revision ID: 011
Revises: 010
Create Date: 2025-06-20 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_dns_zones_tenant_name", "dns_zones", type_="unique")
    op.create_index("ix_dns_zones_name_global", "dns_zones", ["name"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_dns_zones_name_global", table_name="dns_zones")
    op.create_unique_constraint("uq_dns_zones_tenant_name", "dns_zones", ["tenant_id", "name"])
