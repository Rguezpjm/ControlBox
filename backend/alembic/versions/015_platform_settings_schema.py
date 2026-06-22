"""platform settings and resource alerts schema

Revision ID: 015
Revises: 014
Create Date: 2025-06-20 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_platform_settings",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("cpu_threshold_percent", sa.Float(), nullable=False, server_default="90"),
        sa.Column("memory_threshold_percent", sa.Float(), nullable=False, server_default="90"),
        sa.Column("disk_threshold_percent", sa.Float(), nullable=False, server_default="90"),
        sa.Column("alerts_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("alert_cooldown_minutes", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("secrets_rotation_status", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("setup_checklist", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "tenant_resource_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False, server_default="warning"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("current_value", sa.Float(), nullable=False),
        sa.Column("threshold_value", sa.Float(), nullable=False),
        sa.Column("is_acknowledged", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_tenant_resource_alerts_tenant_created", "tenant_resource_alerts", ["tenant_id", "created_at"])
    op.create_index("ix_tenant_resource_alerts_active", "tenant_resource_alerts", ["tenant_id", "is_acknowledged"])

    for code, name in [
        ("platform.read", "Read Platform Settings"),
        ("platform.manage", "Manage Platform Settings"),
    ]:
        op.execute(
            sa.text(
                """
                INSERT INTO permissions (id, code, name, module, created_at, updated_at)
                SELECT gen_random_uuid(), :code, :name, 'platform', now(), now()
                WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = :code)
                """
            ).bindparams(code=code, name=name)
        )

    for slug in ("owner", "administrator"):
        op.execute(
            sa.text(
                """
                INSERT INTO team_permissions (id, team_role_id, permission_code)
                SELECT gen_random_uuid(), tr.id, p.code
                FROM team_roles tr
                CROSS JOIN (VALUES ('platform.read'), ('platform.manage')) AS p(code)
                WHERE tr.slug = :slug
                  AND NOT EXISTS (
                    SELECT 1 FROM team_permissions tp
                    WHERE tp.team_role_id = tr.id AND tp.permission_code = p.code
                  )
                """
            ).bindparams(slug=slug)
        )


def downgrade() -> None:
    op.drop_index("ix_tenant_resource_alerts_active", table_name="tenant_resource_alerts")
    op.drop_index("ix_tenant_resource_alerts_tenant_created", table_name="tenant_resource_alerts")
    op.drop_table("tenant_resource_alerts")
    op.drop_table("tenant_platform_settings")
