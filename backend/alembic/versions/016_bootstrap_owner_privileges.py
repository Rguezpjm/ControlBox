"""Ensure bootstrap admin users have Owner role and platform admin access.

Revision ID: 016
Revises: 015
Create Date: 2025-06-21 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE users
            SET is_platform_admin = true
            WHERE id IN (
                SELECT u.id
                FROM users u
                JOIN user_roles ur ON ur.user_id = u.id
                JOIN roles r ON r.id = ur.role_id AND r.name = 'admin'
                WHERE u.tenant_id IS NOT NULL
            )
            AND is_platform_admin = false
            """
        )
    )

    op.execute(
        sa.text(
            """
            INSERT INTO team_members (id, tenant_id, user_id, team_role_id, status, joined_at, created_at, updated_at)
            SELECT gen_random_uuid(), u.tenant_id, u.id, tr.id, 'active', now(), now(), now()
            FROM users u
            JOIN user_roles ur ON ur.user_id = u.id
            JOIN roles r ON r.id = ur.role_id AND r.name = 'admin'
            JOIN team_roles tr ON tr.slug = 'owner'
            WHERE u.tenant_id IS NOT NULL
            ON CONFLICT (tenant_id, user_id) DO NOTHING
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE team_members tm
            SET team_role_id = tr.id, updated_at = now()
            FROM users u
            JOIN user_roles ur ON ur.user_id = u.id
            JOIN roles r ON r.id = ur.role_id AND r.name = 'admin'
            JOIN team_roles tr ON tr.slug = 'owner'
            WHERE tm.user_id = u.id
              AND tm.tenant_id = u.tenant_id
              AND tm.team_role_id <> tr.id
            """
        )
    )


def downgrade() -> None:
    pass
