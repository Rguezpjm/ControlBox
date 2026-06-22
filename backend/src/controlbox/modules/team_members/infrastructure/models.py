from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from controlbox.modules.identity.infrastructure.models import Base, TimestampMixin


class TeamRoleModel(Base, TimestampMixin):
    __tablename__ = "team_roles"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_system: Mapped[bool] = mapped_column(default=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class TeamPermissionModel(Base):
    __tablename__ = "team_permissions"
    __table_args__ = (
        UniqueConstraint("team_role_id", "permission_code", name="uq_team_permissions_role_code"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    team_role_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("team_roles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    permission_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)


class TeamMemberModel(Base, TimestampMixin):
    __tablename__ = "team_members"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_team_members_tenant_user"),
        Index("ix_team_members_tenant_id", "tenant_id"),
        Index("ix_team_members_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    team_role_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("team_roles.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    invited_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TeamInvitationModel(Base, TimestampMixin):
    __tablename__ = "team_invitations"
    __table_args__ = (
        Index("ix_team_invitations_tenant_id", "tenant_id"),
        Index("ix_team_invitations_email", "email"),
        Index("ix_team_invitations_token_hash", "token_hash"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    team_role_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("team_roles.id", ondelete="RESTRICT"), nullable=False
    )
    invited_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
