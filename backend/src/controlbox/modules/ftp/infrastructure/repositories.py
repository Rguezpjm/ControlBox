from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from controlbox.modules.ftp.domain.entities import FtpAccount
from controlbox.modules.ftp.domain.repositories import FtpAccountRepository
from controlbox.modules.ftp.infrastructure.mappers import to_ftp_account
from controlbox.modules.ftp.infrastructure.models import FtpAccountModel


class SqlAlchemyFtpAccountRepository(FtpAccountRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, account: FtpAccount) -> None:
        model = FtpAccountModel(
            id=account.id,
            tenant_id=account.tenant_id,
            owner_user_id=account.owner_user_id,
            username=account.username,
            system_username=account.system_username,
            password_hash=account.password_hash,
            home_directory=account.home_directory,
            status=account.status.value,
            quota_mb=account.quota_mb,
            max_files=account.max_files,
            upload_bandwidth_kbps=account.upload_bandwidth_kbps,
            download_bandwidth_kbps=account.download_bandwidth_kbps,
            uid=account.uid,
            gid=account.gid,
            last_login_at=account.last_login_at,
            error_message=account.error_message,
        )
        self._session.add(model)

    async def save(self, account: FtpAccount) -> None:
        result = await self._session.execute(
            select(FtpAccountModel).where(FtpAccountModel.id == account.id)
        )
        model = result.scalar_one()
        model.home_directory = account.home_directory
        model.status = account.status.value
        model.quota_mb = account.quota_mb
        model.max_files = account.max_files
        model.upload_bandwidth_kbps = account.upload_bandwidth_kbps
        model.download_bandwidth_kbps = account.download_bandwidth_kbps
        model.password_hash = account.password_hash
        model.last_login_at = account.last_login_at
        model.error_message = account.error_message

    async def get_by_id(self, account_id: UUID) -> FtpAccount | None:
        result = await self._session.execute(
            select(FtpAccountModel).where(FtpAccountModel.id == account_id)
        )
        model = result.scalar_one_or_none()
        return to_ftp_account(model) if model else None

    async def get_by_id_and_tenant(self, account_id: UUID, tenant_id: UUID) -> FtpAccount | None:
        result = await self._session.execute(
            select(FtpAccountModel).where(
                FtpAccountModel.id == account_id,
                FtpAccountModel.tenant_id == tenant_id,
            )
        )
        model = result.scalar_one_or_none()
        return to_ftp_account(model) if model else None

    async def get_by_username(self, username: str, tenant_id: UUID) -> FtpAccount | None:
        result = await self._session.execute(
            select(FtpAccountModel).where(
                FtpAccountModel.username == username,
                FtpAccountModel.tenant_id == tenant_id,
            )
        )
        model = result.scalar_one_or_none()
        return to_ftp_account(model) if model else None

    async def list_by_tenant(self, tenant_id: UUID) -> list[FtpAccount]:
        result = await self._session.execute(
            select(FtpAccountModel)
            .where(FtpAccountModel.tenant_id == tenant_id)
            .order_by(FtpAccountModel.created_at.desc())
        )
        return [to_ftp_account(model) for model in result.scalars().all()]

    async def list_active(self) -> list[FtpAccount]:
        result = await self._session.execute(
            select(FtpAccountModel)
            .where(FtpAccountModel.status == "active")
            .order_by(FtpAccountModel.created_at.desc())
        )
        return [to_ftp_account(model) for model in result.scalars().all()]

    async def delete(self, account_id: UUID) -> None:
        await self._session.execute(delete(FtpAccountModel).where(FtpAccountModel.id == account_id))
