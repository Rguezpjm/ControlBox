"""streaming schema

Revision ID: 023
Revises: 022
Create Date: 2026-06-24 13:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Sources table
    op.create_table(
        "streaming_sources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),  # "m3u" or "xtream"
        sa.Column("url", sa.String(512), nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("password", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_streaming_sources_tenant_id", "streaming_sources", ["tenant_id"])

    # 2. Categories table
    op.create_table(
        "streaming_categories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_streaming_categories_tenant_id", "streaming_categories", ["tenant_id"])

    # 3. Channels table
    op.create_table(
        "streaming_channels",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), sa.ForeignKey("streaming_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", UUID(as_uuid=True), sa.ForeignKey("streaming_categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("stream_url", sa.String(512), nullable=False),
        sa.Column("logo_url", sa.String(512), nullable=True),
        sa.Column("epg_id", sa.String(255), nullable=True),
        sa.Column("stream_id", sa.Integer, nullable=True),  # External ID from Xtream Codes
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.String(32), nullable=False, server_default="unknown"),  # "online", "offline", "unknown"
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_streaming_channels_tenant_id", "streaming_channels", ["tenant_id"])
    op.create_index("ix_streaming_channels_source_id", "streaming_channels", ["source_id"])
    op.create_index("ix_streaming_channels_category_id", "streaming_channels", ["category_id"])

    # 4. Clients / Users allowed to stream
    op.create_table(
        "streaming_clients",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("password", sa.String(64), nullable=False),
        sa.Column("max_connections", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("allowed_categories", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_streaming_clients_tenant_id", "streaming_clients", ["tenant_id"])
    op.create_index("ix_streaming_clients_username", "streaming_clients", ["username"])
    op.create_index(
        "uq_streaming_clients_tenant_username",
        "streaming_clients",
        ["tenant_id", "username"],
        unique=True,
    )

    # 5. Connections tracking
    op.create_table(
        "streaming_connections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", UUID(as_uuid=True), sa.ForeignKey("streaming_clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel_id", UUID(as_uuid=True), sa.ForeignKey("streaming_channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=False),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("bytes_transferred", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("connected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_streaming_connections_tenant_id", "streaming_connections", ["tenant_id"])
    op.create_index("ix_streaming_connections_client_id", "streaming_connections", ["client_id"])
    op.create_index("ix_streaming_connections_channel_id", "streaming_connections", ["channel_id"])

    # 6. EPG Cache table
    op.create_table(
        "streaming_epg",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel_epg_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_streaming_epg_tenant_id", "streaming_epg", ["tenant_id"])
    op.create_index("ix_streaming_epg_channel_epg_id", "streaming_epg", ["channel_epg_id"])
    op.create_index("ix_streaming_epg_times", "streaming_epg", ["start_time", "end_time"])

    # 7. Add permissions
    for code, name in [
        ("streaming.read", "Read Streaming Settings"),
        ("streaming.manage", "Manage Streaming Setup"),
    ]:
        op.execute(
            sa.text(
                """
                INSERT INTO permissions (id, code, name, module, created_at, updated_at)
                SELECT gen_random_uuid(), :code, :name, 'streaming', now(), now()
                WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = :code)
                """
            ).bindparams(code=code, name=name)
        )


def downgrade() -> None:
    op.drop_table("streaming_epg")
    op.drop_table("streaming_connections")
    op.drop_table("streaming_clients")
    op.drop_table("streaming_channels")
    op.drop_table("streaming_categories")
    op.drop_table("streaming_sources")
