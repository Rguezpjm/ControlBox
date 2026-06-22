"""tenant mail service and mailboxes

Revision ID: 018
Revises: 017
Create Date: 2025-06-21 18:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_mail_services",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("mail_domain", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("imap_host", sa.String(255), nullable=False, server_default=""),
        sa.Column("imap_port", sa.Integer(), nullable=False, server_default="993"),
        sa.Column("imap_use_ssl", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("smtp_host", sa.String(255), nullable=False, server_default=""),
        sa.Column("smtp_port", sa.Integer(), nullable=False, server_default="587"),
        sa.Column("smtp_use_ssl", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("smtp_use_tls", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("admin_username", sa.String(255), nullable=False, server_default=""),
        sa.Column("admin_password_enc", sa.Text(), nullable=True),
        sa.Column("default_quota_mb", sa.Integer(), nullable=False, server_default="5120"),
        sa.Column("total_quota_mb", sa.Integer(), nullable=False, server_default="51200"),
        sa.Column("webmail_url", sa.String(512), nullable=True),
        sa.Column("connection_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tenant_mail_services_tenant_id", "tenant_mail_services", ["tenant_id"], unique=True)
    op.create_index("ix_tenant_mail_services_mail_domain", "tenant_mail_services", ["mail_domain"])

    op.create_table(
        "mail_accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mail_service_id", UUID(as_uuid=True), sa.ForeignKey("tenant_mail_services.id", ondelete="CASCADE"), nullable=False),
        sa.Column("local_part", sa.String(64), nullable=False),
        sa.Column("email_address", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("quota_mb", sa.Integer(), nullable=False, server_default="5120"),
        sa.Column("used_mb", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("forwarding_to", sa.String(255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("mail_service_id", "local_part", name="uq_mail_accounts_service_local_part"),
        sa.UniqueConstraint("email_address", name="uq_mail_accounts_email_address"),
    )
    op.create_index("ix_mail_accounts_tenant_id", "mail_accounts", ["tenant_id"])
    op.create_index("ix_mail_accounts_mail_service_id", "mail_accounts", ["mail_service_id"])

    for code, name in [
        ("mail.read", "Read Mail"),
        ("mail.manage", "Manage Mail"),
    ]:
        op.execute(
            sa.text(
                """
                INSERT INTO permissions (id, code, name, module, created_at, updated_at)
                SELECT gen_random_uuid(), :code, :name, 'mail', now(), now()
                WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = :code)
                """
            ).bindparams(code=code, name=name)
        )

    for code in ("mail.read", "mail.manage"):
        op.execute(
            sa.text(
                """
                INSERT INTO team_permissions (id, team_role_id, permission_code)
                SELECT gen_random_uuid(), tr.id, :code
                FROM team_roles tr
                WHERE tr.slug IN ('owner', 'administrator')
                  AND NOT EXISTS (
                      SELECT 1 FROM team_permissions tp
                      WHERE tp.team_role_id = tr.id AND tp.permission_code = :code
                  )
                """
            ).bindparams(code=code)
        )


def downgrade() -> None:
    op.drop_index("ix_mail_accounts_mail_service_id", table_name="mail_accounts")
    op.drop_index("ix_mail_accounts_tenant_id", table_name="mail_accounts")
    op.drop_table("mail_accounts")
    op.drop_index("ix_tenant_mail_services_mail_domain", table_name="tenant_mail_services")
    op.drop_index("ix_tenant_mail_services_tenant_id", table_name="tenant_mail_services")
    op.drop_table("tenant_mail_services")
