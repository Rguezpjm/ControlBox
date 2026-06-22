"""wordpress schema

Revision ID: 012
Revises: 011
Create Date: 2025-06-19 22:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wordpress_sites",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("php_version", sa.String(16), nullable=False, server_default="8.3"),
        sa.Column("wordpress_version", sa.String(32), nullable=False, server_default="latest"),
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
        sa.Column("parent_site_id", UUID(as_uuid=True), sa.ForeignKey("wordpress_sites.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_staging", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("settings", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("task_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_wordpress_sites_tenant_id", "wordpress_sites", ["tenant_id"])
    op.create_index("ix_wordpress_sites_domain", "wordpress_sites", ["domain"])
    op.create_index("ix_wordpress_sites_status", "wordpress_sites", ["status"])
    op.create_index(
        "uq_wordpress_sites_tenant_domain",
        "wordpress_sites",
        ["tenant_id", "domain"],
        unique=True,
    )

    op.create_table(
        "wordpress_backups",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("site_id", UUID(as_uuid=True), sa.ForeignKey("wordpress_sites.id", ondelete="CASCADE"), nullable=False),
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
    op.create_index("ix_wordpress_backups_site_id", "wordpress_backups", ["site_id"])

    for code, name in [
        ("wordpress.read", "Read WordPress Sites"),
        ("wordpress.manage", "Manage WordPress Sites"),
    ]:
        op.execute(
            sa.text(
                """
                INSERT INTO permissions (id, code, name, module, created_at, updated_at)
                SELECT gen_random_uuid(), :code, :name, 'wordpress', now(), now()
                WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = :code)
                """
            ).bindparams(code=code, name=name)
        )


def downgrade() -> None:
    op.drop_table("wordpress_backups")
    op.drop_table("wordpress_sites")
