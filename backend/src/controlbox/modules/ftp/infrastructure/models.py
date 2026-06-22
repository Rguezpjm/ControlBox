from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from controlbox.modules.identity.infrastructure.models import Base


class FtpAccountModel(Base):
    __tablename__ = "ftp_accounts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    system_username: Mapped[str] = mapped_column(String(96), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    home_directory: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    quota_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    upload_bandwidth_kbps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    download_bandwidth_kbps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    uid: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    gid: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
