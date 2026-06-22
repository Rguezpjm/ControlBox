"""dns schema

Revision ID: 005
Revises: 004
Create Date: 2025-06-19 18:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dns_zones",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("serial", sa.Integer(), nullable=False),
        sa.Column("soa_email", sa.String(length=128), nullable=False),
        sa.Column("default_ttl", sa.Integer(), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("nameservers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_dns_zones_tenant_name"),
    )
    op.create_index("ix_dns_zones_tenant_id", "dns_zones", ["tenant_id"])
    op.create_index("ix_dns_zones_status", "dns_zones", ["status"])

    op.create_table(
        "dns_api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("scopes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dns_api_keys_prefix", "dns_api_keys", ["key_prefix"])

    op.execute(
        sa.text("""
            INSERT INTO permissions (id, code, name, module, created_at, updated_at)
            SELECT gen_random_uuid(), 'dns.read', 'Read DNS', 'dns', now(), now()
            WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'dns.read')
        """)
    )
    op.execute(
        sa.text("""
            INSERT INTO permissions (id, code, name, module, created_at, updated_at)
            SELECT gen_random_uuid(), 'dns.manage', 'Manage DNS', 'dns', now(), now()
            WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'dns.manage')
        """)
    )


def downgrade() -> None:
    op.drop_index("ix_dns_api_keys_prefix", table_name="dns_api_keys")
    op.drop_table("dns_api_keys")
    op.drop_index("ix_dns_zones_status", table_name="dns_zones")
    op.drop_index("ix_dns_zones_tenant_id", table_name="dns_zones")
    op.drop_table("dns_zones")
