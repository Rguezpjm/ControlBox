"""team members schema

Revision ID: 013
Revises: 012
Create Date: 2025-06-20 10:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLE_DEFS = {
    "owner": ("Owner", "Full account access", 100, ["*"]),
    "administrator": ("Administrator", "Full access except billing", 90, [
        "tenants.read", "users.read", "users.manage", "roles.read", "roles.manage",
        "sessions.read", "sessions.manage", "audit.read", "team_members.read", "team_members.manage",
        "websites.read", "websites.manage", "wordpress.read", "wordpress.manage",
        "databases.read", "databases.manage", "supabase.read", "supabase.manage",
        "dns.read", "dns.manage", "files.read", "files.manage", "ftp.read", "ftp.manage",
        "backups.read", "backups.manage", "monitoring.read", "security.read", "security.manage",
        "staging.read", "staging.manage",
    ]),
        "website_manager": ("Website Manager", "Manage websites and statistics", 50, [
        "websites.read", "websites.manage", "wordpress.read", "wordpress.manage",
        "staging.read", "staging.manage", "monitoring.read", "files.read",
    ]),
    "dns_manager": ("DNS Manager", "Manage DNS records", 50, ["dns.read", "dns.manage"]),
    "database_manager": ("Database Manager", "Manage databases and backups", 50, [
        "databases.read", "databases.manage", "backups.read",
    ]),
    "ftp_manager": ("FTP Manager", "Manage FTP and files", 50, [
        "ftp.read", "ftp.manage", "files.read", "files.manage",
    ]),
    "billing_manager": ("Billing Manager", "Manage billing", 60, [
        "billing.read", "billing.manage", "tenants.read", "audit.read",
    ]),
    "read_only": ("Read Only", "View-only access", 10, [
        "tenants.read", "users.read", "roles.read", "sessions.read", "audit.read",
        "team_members.read", "websites.read", "wordpress.read", "databases.read",
        "supabase.read", "dns.read", "files.read", "ftp.read", "backups.read",
        "monitoring.read", "security.read", "billing.read",
    ]),
}


def upgrade() -> None:
    op.create_table(
        "team_roles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("level", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "team_permissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_role_id", UUID(as_uuid=True), sa.ForeignKey("team_roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission_code", sa.String(128), nullable=False),
        sa.UniqueConstraint("team_role_id", "permission_code", name="uq_team_permissions_role_code"),
    )
    op.create_index("ix_team_permissions_role_id", "team_permissions", ["team_role_id"])

    op.create_table(
        "team_members",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_role_id", UUID(as_uuid=True), sa.ForeignKey("team_roles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("invited_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_team_members_tenant_user"),
    )
    op.create_index("ix_team_members_tenant_id", "team_members", ["tenant_id"])

    op.create_table(
        "team_invitations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("team_role_id", UUID(as_uuid=True), sa.ForeignKey("team_roles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("invited_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_team_invitations_tenant_id", "team_invitations", ["tenant_id"])
    op.create_index("ix_team_invitations_token_hash", "team_invitations", ["token_hash"])

    for code, name in [
        ("team_members.read", "Read Team Members"),
        ("team_members.manage", "Manage Team Members"),
        ("billing.read", "Read Billing"),
        ("billing.manage", "Manage Billing"),
    ]:
        op.execute(
            sa.text(
                """
                INSERT INTO permissions (id, code, name, module, created_at, updated_at)
                SELECT gen_random_uuid(), :code, :name, :module, now(), now()
                WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = :code)
                """
            ).bindparams(code=code, name=name, module=code.split(".")[0])
        )

    for slug, (name, desc, level, perms) in ROLE_DEFS.items():
        op.execute(
            sa.text(
                """
                INSERT INTO team_roles (id, slug, name, description, is_system, level, created_at, updated_at)
                VALUES (gen_random_uuid(), :slug, :name, :desc, true, :level, now(), now())
                """
            ).bindparams(slug=slug, name=name, desc=desc, level=level)
        )
        for perm in perms:
            op.execute(
                sa.text(
                    """
                    INSERT INTO team_permissions (id, team_role_id, permission_code)
                    SELECT gen_random_uuid(), tr.id, :code
                    FROM team_roles tr
                    WHERE tr.slug = :slug
                      AND NOT EXISTS (
                          SELECT 1 FROM team_permissions tp
                          WHERE tp.team_role_id = tr.id AND tp.permission_code = :code
                      )
                    """
                ).bindparams(slug=slug, code=perm)
            )

    op.execute(
        sa.text(
            """
            INSERT INTO team_members (id, tenant_id, user_id, team_role_id, status, joined_at, created_at, updated_at)
            SELECT gen_random_uuid(), u.tenant_id, u.id, tr.id, 'active', now(), now(), now()
            FROM users u
            JOIN user_roles ur ON ur.user_id = u.id
            JOIN roles r ON r.id = ur.role_id AND r.name = 'admin'
            JOIN team_roles tr ON tr.slug = 'owner'
            WHERE u.tenant_id IS NOT NULL
            ON CONFLICT (tenant_id, user_id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_table("team_invitations")
    op.drop_table("team_members")
    op.drop_table("team_permissions")
    op.drop_table("team_roles")
