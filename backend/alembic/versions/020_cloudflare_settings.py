"""cloudflare integration settings columns

Revision ID: 020
Revises: 019
Create Date: 2026-06-22 22:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenant_platform_settings",
        sa.Column("cloudflare_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "tenant_platform_settings",
        sa.Column("cloudflare_api_token_enc", sa.Text(), nullable=True),
    )
    op.add_column(
        "tenant_platform_settings",
        sa.Column("cloudflare_account_id", sa.String(64), nullable=True),
    )
    op.add_column(
        "tenant_platform_settings",
        sa.Column("cloudflare_tunnel_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "tenant_platform_settings",
        sa.Column("cloudflare_tunnel_id", sa.String(64), nullable=True),
    )
    op.add_column(
        "tenant_platform_settings",
        sa.Column("cloudflare_tunnel_token_enc", sa.Text(), nullable=True),
    )
    op.add_column(
        "tenant_platform_settings",
        sa.Column("cloudflare_tunnel_hostname", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenant_platform_settings", "cloudflare_tunnel_hostname")
    op.drop_column("tenant_platform_settings", "cloudflare_tunnel_token_enc")
    op.drop_column("tenant_platform_settings", "cloudflare_tunnel_id")
    op.drop_column("tenant_platform_settings", "cloudflare_tunnel_enabled")
    op.drop_column("tenant_platform_settings", "cloudflare_account_id")
    op.drop_column("tenant_platform_settings", "cloudflare_api_token_enc")
    op.drop_column("tenant_platform_settings", "cloudflare_enabled")
