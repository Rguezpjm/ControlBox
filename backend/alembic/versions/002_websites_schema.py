"""websites schema

Revision ID: 002
Revises: 001
Create Date: 2025-06-19 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "websites",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("runtime", sa.String(length=32), nullable=False),
        sa.Column("runtime_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("container_id", sa.String(length=128), nullable=True),
        sa.Column("container_name", sa.String(length=128), nullable=True),
        sa.Column("document_root", sa.String(length=512), nullable=False),
        sa.Column("ssl_enabled", sa.Boolean(), nullable=False),
        sa.Column("ssl_status", sa.String(length=32), nullable=False),
        sa.Column("database_engine", sa.String(length=32), nullable=False),
        sa.Column("database_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("monitoring_enabled", sa.Boolean(), nullable=False),
        sa.Column("logs_enabled", sa.Boolean(), nullable=False),
        sa.Column("logs_path", sa.String(length=512), nullable=True),
        sa.Column("traefik_router", sa.String(length=128), nullable=True),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("disk_used_mb", sa.Integer(), nullable=False),
        sa.Column("disk_limit_mb", sa.Integer(), nullable=False),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "domain", name="uq_websites_tenant_domain"),
    )
    op.create_index("ix_websites_tenant_id", "websites", ["tenant_id"])
    op.create_index("ix_websites_domain", "websites", ["domain"])
    op.create_index("ix_websites_status", "websites", ["status"])

    permissions = sa.table(
        "permissions",
        sa.column("id", postgresql.UUID),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("module", sa.String),
    )
    op.execute(
        sa.text("""
            INSERT INTO permissions (id, code, name, module, created_at, updated_at)
            SELECT gen_random_uuid(), 'websites.read', 'Read Websites', 'websites', now(), now()
            WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'websites.read')
        """)
    )
    op.execute(
        sa.text("""
            INSERT INTO permissions (id, code, name, module, created_at, updated_at)
            SELECT gen_random_uuid(), 'websites.manage', 'Manage Websites', 'websites', now(), now()
            WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'websites.manage')
        """)
    )


def downgrade() -> None:
    op.drop_index("ix_websites_status", table_name="websites")
    op.drop_index("ix_websites_domain", table_name="websites")
    op.drop_index("ix_websites_tenant_id", table_name="websites")
    op.drop_table("websites")
    op.execute(sa.text("DELETE FROM permissions WHERE code IN ('websites.read', 'websites.manage')"))
