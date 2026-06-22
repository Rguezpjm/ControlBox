"""ftp schema

Revision ID: 007
Revises: 006
Create Date: 2025-06-19 22:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ftp_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("system_username", sa.String(length=96), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("home_directory", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("quota_mb", sa.Integer(), nullable=False),
        sa.Column("max_files", sa.Integer(), nullable=False),
        sa.Column("upload_bandwidth_kbps", sa.Integer(), nullable=False),
        sa.Column("download_bandwidth_kbps", sa.Integer(), nullable=False),
        sa.Column("uid", sa.Integer(), nullable=False),
        sa.Column("gid", sa.Integer(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "username", name="uq_ftp_accounts_tenant_username"),
        sa.UniqueConstraint("system_username", name="uq_ftp_accounts_system_username"),
    )
    op.create_index("ix_ftp_accounts_tenant_id", "ftp_accounts", ["tenant_id"])
    op.create_index("ix_ftp_accounts_status", "ftp_accounts", ["status"])

    op.execute(
        sa.text("""
            INSERT INTO permissions (id, code, name, module, created_at, updated_at)
            SELECT gen_random_uuid(), 'ftp.read', 'Read FTP', 'ftp', now(), now()
            WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'ftp.read')
        """)
    )
    op.execute(
        sa.text("""
            INSERT INTO permissions (id, code, name, module, created_at, updated_at)
            SELECT gen_random_uuid(), 'ftp.manage', 'Manage FTP', 'ftp', now(), now()
            WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'ftp.manage')
        """)
    )


def downgrade() -> None:
    op.drop_index("ix_ftp_accounts_status", table_name="ftp_accounts")
    op.drop_index("ix_ftp_accounts_tenant_id", table_name="ftp_accounts")
    op.drop_table("ftp_accounts")
