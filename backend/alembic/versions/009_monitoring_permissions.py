"""monitoring permissions

Revision ID: 009
Revises: 008
Create Date: 2025-06-20 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text("""
            INSERT INTO permissions (id, code, name, module, created_at, updated_at)
            SELECT gen_random_uuid(), 'monitoring.read', 'Read Monitoring', 'monitoring', now(), now()
            WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'monitoring.read')
        """)
    )


def downgrade() -> None:
    pass
