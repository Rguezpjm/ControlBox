from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from controlbox.modules.identity.infrastructure.models import Base, TimestampMixin


class WordPressSiteModel(Base, TimestampMixin):
    __tablename__ = "wordpress_sites"
    __table_args__ = (
        Index("ix_wordpress_sites_tenant_id", "tenant_id"),
        Index("ix_wordpress_sites_domain", "domain"),
        Index("ix_wordpress_sites_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    php_version: Mapped[str] = mapped_column(String(16), nullable=False, default="8.3")
    wordpress_version: Mapped[str] = mapped_column(String(32), nullable=False, default="latest")
    url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    admin_user: Mapped[str] = mapped_column(String(64), nullable=False)
    admin_email: Mapped[str] = mapped_column(String(255), nullable=False)
    managed_database_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    database_user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    nginx_container_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    php_container_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    site_path: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    ssl_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ssl_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    maintenance_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    disk_used_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    db_size_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parent_site_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("wordpress_sites.id", ondelete="SET NULL"), nullable=True
    )
    is_staging: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class WordPressBackupModel(Base, TimestampMixin):
    __tablename__ = "wordpress_backups"
    __table_args__ = (Index("ix_wordpress_backups_site_id", "site_id"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    site_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("wordpress_sites.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    size_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    includes_database: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    includes_files: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
