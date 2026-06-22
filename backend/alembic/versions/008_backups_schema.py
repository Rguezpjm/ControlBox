"""backups schema

Revision ID: 008
Revises: 007
Create Date: 2025-06-19 23:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "backup_destinations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("destination_type", sa.String(length=16), nullable=False),
        sa.Column("bucket", sa.String(length=128), nullable=False),
        sa.Column("endpoint", sa.String(length=512), nullable=False),
        sa.Column("region", sa.String(length=64), nullable=False),
        sa.Column("prefix", sa.String(length=256), nullable=False),
        sa.Column("local_path", sa.String(length=512), nullable=False),
        sa.Column("access_key_encrypted", sa.Text(), nullable=False),
        sa.Column("secret_key_encrypted", sa.Text(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_backup_destinations_tenant_name"),
    )
    op.create_index("ix_backup_destinations_tenant_id", "backup_destinations", ["tenant_id"])

    op.create_table(
        "backup_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("destination_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cron_expression", sa.String(length=64), nullable=False),
        sa.Column("max_versions", sa.Integer(), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["destination_id"], ["backup_destinations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_backup_schedules_tenant_id", "backup_schedules", ["tenant_id"])
    op.create_index("ix_backup_schedules_next_run", "backup_schedules", ["next_run_at"])

    op.create_table(
        "backup_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("destination_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resource_name", sa.String(length=128), nullable=False),
        sa.Column("resource_key", sa.String(length=256), nullable=False),
        sa.Column("trigger_type", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["schedule_id"], ["backup_schedules.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["destination_id"], ["backup_destinations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_backup_jobs_tenant_id", "backup_jobs", ["tenant_id"])
    op.create_index("ix_backup_jobs_resource_key", "backup_jobs", ["tenant_id", "resource_key"])
    op.create_index("ix_backup_jobs_status", "backup_jobs", ["status"])

    op.execute(
        sa.text("""
            INSERT INTO permissions (id, code, name, module, created_at, updated_at)
            SELECT gen_random_uuid(), 'backups.read', 'Read Backups', 'backups', now(), now()
            WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'backups.read')
        """)
    )
    op.execute(
        sa.text("""
            INSERT INTO permissions (id, code, name, module, created_at, updated_at)
            SELECT gen_random_uuid(), 'backups.manage', 'Manage Backups', 'backups', now(), now()
            WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'backups.manage')
        """)
    )


def downgrade() -> None:
    op.drop_index("ix_backup_jobs_status", table_name="backup_jobs")
    op.drop_index("ix_backup_jobs_resource_key", table_name="backup_jobs")
    op.drop_index("ix_backup_jobs_tenant_id", table_name="backup_jobs")
    op.drop_table("backup_jobs")
    op.drop_index("ix_backup_schedules_next_run", table_name="backup_schedules")
    op.drop_index("ix_backup_schedules_tenant_id", table_name="backup_schedules")
    op.drop_table("backup_schedules")
    op.drop_index("ix_backup_destinations_tenant_id", table_name="backup_destinations")
    op.drop_table("backup_destinations")
