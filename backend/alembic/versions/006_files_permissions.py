"""files permissions

Revision ID: 006
Revises: 005
Create Date: 2025-06-19 20:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text("""
            INSERT INTO permissions (id, code, name, module, created_at, updated_at)
            SELECT gen_random_uuid(), 'files.read', 'Read Files', 'files', now(), now()
            WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'files.read')
        """)
    )
    op.execute(
        sa.text("""
            INSERT INTO permissions (id, code, name, module, created_at, updated_at)
            SELECT gen_random_uuid(), 'files.manage', 'Manage Files', 'files', now(), now()
            WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'files.manage')
        """)
    )


def downgrade() -> None:
    pass
