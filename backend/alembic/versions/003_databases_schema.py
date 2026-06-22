"""databases schema

Revision ID: 003
Revises: 002
Create Date: 2025-06-19 14:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "managed_databases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("engine", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("database_name", sa.String(length=128), nullable=False),
        sa.Column("charset", sa.String(length=32), nullable=False),
        sa.Column("db_collation", sa.String(length=64), nullable=False),
        sa.Column("max_connections", sa.Integer(), nullable=False),
        sa.Column("size_mb", sa.Integer(), nullable=False),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_managed_databases_tenant_name"),
    )
    op.create_index("ix_managed_databases_tenant_id", "managed_databases", ["tenant_id"])
    op.create_index("ix_managed_databases_engine", "managed_databases", ["engine"])
    op.create_index("ix_managed_databases_status", "managed_databases", ["status"])

    op.create_table(
        "database_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("database_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("host", sa.String(length=64), nullable=False),
        sa.Column("max_connections", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("grants", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["database_id"], ["managed_databases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("database_id", "username", name="uq_database_users_db_username"),
    )
    op.create_index("ix_database_users_database_id", "database_users", ["database_id"])

    op.create_table(
        "database_backups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("database_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("backup_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=True),
        sa.Column("size_mb", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["database_id"], ["managed_databases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_database_backups_database_id", "database_backups", ["database_id"])

    op.execute(
        sa.text("""
            INSERT INTO permissions (id, code, name, module, created_at, updated_at)
            SELECT gen_random_uuid(), 'databases.read', 'Read Databases', 'databases', now(), now()
            WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'databases.read')
        """)
    )
    op.execute(
        sa.text("""
            INSERT INTO permissions (id, code, name, module, created_at, updated_at)
            SELECT gen_random_uuid(), 'databases.manage', 'Manage Databases', 'databases', now(), now()
            WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'databases.manage')
        """)
    )


def downgrade() -> None:
    op.drop_index("ix_database_backups_database_id", table_name="database_backups")
    op.drop_table("database_backups")
    op.drop_index("ix_database_users_database_id", table_name="database_users")
    op.drop_table("database_users")
    op.drop_index("ix_managed_databases_status", table_name="managed_databases")
    op.drop_index("ix_managed_databases_engine", table_name="managed_databases")
    op.drop_index("ix_managed_databases_tenant_id", table_name="managed_databases")
    op.drop_table("managed_databases")
