"""telegram alert settings columns

Revision ID: 019
Revises: 018
Create Date: 2026-06-21 22:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenant_platform_settings",
        sa.Column("telegram_alerts_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "tenant_platform_settings",
        sa.Column("telegram_bot_token_enc", sa.Text(), nullable=True),
    )
    op.add_column(
        "tenant_platform_settings",
        sa.Column("telegram_chat_id", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenant_platform_settings", "telegram_chat_id")
    op.drop_column("tenant_platform_settings", "telegram_bot_token_enc")
    op.drop_column("tenant_platform_settings", "telegram_alerts_enabled")
