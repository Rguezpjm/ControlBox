"""joomla schema

Revision ID: 022
Revises: 021
Create Date: 2026-06-24 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "joomla_sites",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("php_version", sa.String(16), nullable=False, server_default="8.3"),
        sa.Column("joomla_version", sa.String(32), nullable=False, server_default="5.1.1"),
        sa.Column("url", sa.String(512), nullable=False, server_default=""),
        sa.Column("admin_user", sa.String(64), nullable=False),
        sa.Column("admin_email", sa.String(255), nullable=False),
        sa.Column("managed_database_id", UUID(as_uuid=True), nullable=True),
        sa.Column("database_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("nginx_container_name", sa.String(128), nullable=True),
        sa.Column("php_container_name", sa.String(128), nullable=True),
        sa.Column("site_path", sa.String(512), nullable=False, server_default=""),
        sa.Column("ssl_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("ssl_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("maintenance_mode", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("disk_used_mb", sa.Integer, nullable=False, server_default="0"),
        sa.Column("db_size_mb", sa.Integer, nullable=False, server_default="0"),
        sa.Column("parent_site_id", UUID(as_uuid=True), sa.ForeignKey("joomla_sites.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_staging", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("settings", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("task_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_joomla_sites_tenant_id", "joomla_sites", ["tenant_id"])
    op.create_index("ix_joomla_sites_domain", "joomla_sites", ["domain"])
    op.create_index("ix_joomla_sites_status", "joomla_sites", ["status"])
    op.create_index("ix_joomla_sites_owner_user_id", "joomla_sites", ["owner_user_id"])
    op.create_index(
        "uq_joomla_sites_tenant_domain",
        "joomla_sites",
        ["tenant_id", "domain"],
        unique=True,
    )

    op.create_table(
        "joomla_backups",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("site_id", UUID(as_uuid=True), sa.ForeignKey("joomla_sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("file_path", sa.String(512), nullable=True),
        sa.Column("size_mb", sa.Integer, nullable=False, server_default="0"),
        sa.Column("checksum", sa.String(128), nullable=True),
        sa.Column("includes_database", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("includes_files", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_joomla_backups_site_id", "joomla_backups", ["site_id"])

    for code, name in [
        ("joomla.read", "Read Joomla Sites"),
        ("joomla.manage", "Manage Joomla Sites"),
    ]:
        op.execute(
            sa.text(
                """
                INSERT INTO permissions (id, code, name, module, created_at, updated_at)
                SELECT gen_random_uuid(), :code, :name, 'joomla', now(), now()
                WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = :code)
                """
            ).bindparams(code=code, name=name)
        )


def downgrade() -> None:
    op.drop_table("joomla_backups")
    op.drop_table("joomla_sites")
