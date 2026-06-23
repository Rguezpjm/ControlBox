from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from controlbox.modules.identity.infrastructure.models import Base, TimestampMixin


class WebsiteModel(Base, TimestampMixin):
    __tablename__ = "websites"
    __table_args__ = (
        Index("ix_websites_tenant_id", "tenant_id"),
        Index("ix_websites_domain", "domain"),
        Index("ix_websites_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    runtime: Mapped[str] = mapped_column(String(32), nullable=False)
    runtime_version: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    container_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    container_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    document_root: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    ssl_enabled: Mapped[bool] = mapped_column(default=True)
    ssl_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    database_engine: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    database_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    monitoring_enabled: Mapped[bool] = mapped_column(default=True)
    logs_enabled: Mapped[bool] = mapped_column(default=True)
    logs_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    traefik_router: Mapped[str | None] = mapped_column(String(128), nullable=True)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    disk_used_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    disk_limit_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=5120)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
