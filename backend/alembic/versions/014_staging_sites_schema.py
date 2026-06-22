"""staging sites schema

Revision ID: 014
Revises: 013
Create Date: 2025-06-20 14:00:00.000000
"""

from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "staging_sites",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), nullable=False),
        sa.Column("source_domain", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("domain_mode", sa.String(32), nullable=False, server_default="subdomain"),
        sa.Column("stack_type", sa.String(32), nullable=False),
        sa.Column("runtime_version", sa.String(32), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("ssl_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("ssl_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("container_name", sa.String(128), nullable=True),
        sa.Column("nginx_container_name", sa.String(128), nullable=True),
        sa.Column("php_container_name", sa.String(128), nullable=True),
        sa.Column("site_path", sa.String(512), nullable=False, server_default=""),
        sa.Column("traefik_router", sa.String(128), nullable=True),
        sa.Column("managed_database_id", UUID(as_uuid=True), nullable=True),
        sa.Column("database_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("database_config", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("public_access_blocked", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_type", sa.String(32), nullable=True),
        sa.Column("last_sync_direction", sa.String(32), nullable=True),
        sa.Column("cpu_usage_percent", sa.Float, nullable=False, server_default="0"),
        sa.Column("memory_used_mb", sa.Integer, nullable=False, server_default="0"),
        sa.Column("disk_used_mb", sa.Integer, nullable=False, server_default="0"),
        sa.Column("settings", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("task_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_staging_sites_tenant_id", "staging_sites", ["tenant_id"])
    op.create_index("ix_staging_sites_source", "staging_sites", ["source_type", "source_id"])
    op.create_index("ix_staging_sites_domain", "staging_sites", ["domain"])
    op.create_index("ix_staging_sites_status", "staging_sites", ["status"])

    permissions = sa.table(
        "permissions",
        sa.column("id", UUID),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("module", sa.String),
    )
    op.bulk_insert(
        permissions,
        [
            {"id": uuid4(), "code": "staging.read", "name": "Read Staging", "module": "staging"},
            {"id": uuid4(), "code": "staging.manage", "name": "Manage Staging", "module": "staging"},
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code IN ('staging.read', 'staging.manage')")
    op.drop_index("ix_staging_sites_status", table_name="staging_sites")
    op.drop_index("ix_staging_sites_domain", table_name="staging_sites")
    op.drop_index("ix_staging_sites_source", table_name="staging_sites")
    op.drop_index("ix_staging_sites_tenant_id", table_name="staging_sites")
    op.drop_table("staging_sites")
