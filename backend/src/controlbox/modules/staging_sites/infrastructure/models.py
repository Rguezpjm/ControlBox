from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Float, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from controlbox.modules.identity.infrastructure.models import Base, TimestampMixin


class StagingSiteModel(Base, TimestampMixin):
    __tablename__ = "staging_sites"
    __table_args__ = (
        Index("ix_staging_sites_tenant_id", "tenant_id"),
        Index("ix_staging_sites_source", "source_type", "source_id"),
        Index("ix_staging_sites_domain", "domain"),
        Index("ix_staging_sites_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_domain: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    domain_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="subdomain")
    stack_type: Mapped[str] = mapped_column(String(32), nullable=False)
    runtime_version: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    ssl_enabled: Mapped[bool] = mapped_column(default=True)
    ssl_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    container_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    nginx_container_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    php_container_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    site_path: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    traefik_router: Mapped[str | None] = mapped_column(String(128), nullable=True)
    managed_database_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    database_user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    database_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    public_access_blocked: Mapped[bool] = mapped_column(default=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_sync_direction: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cpu_usage_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    memory_used_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    disk_used_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
