from uuid import UUID

from controlbox.config.settings import Settings, get_settings
from controlbox.modules.databases.infrastructure.engine_adapters import generate_password, hash_password
from controlbox.modules.ftp.application.commands import (
    ChangeFtpPasswordCommand,
    CreateFtpAccountCommand,
    DeleteFtpAccountCommand,
    SetFtpDirectoryCommand,
    SetFtpQuotaCommand,
    SetFtpStatusCommand,
    UpdateFtpAccountCommand,
)
from controlbox.modules.ftp.domain.entities import FtpAccount, FtpAccountStatus
from controlbox.modules.ftp.domain.services import FtpDomainService
from controlbox.modules.ftp.infrastructure.provisioner import PureFtpdProvisioner
from controlbox.modules.ftp.infrastructure.service_manager import FtpServiceManager
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import NotFoundError, ValidationError


async def _sync_sftp_account(
    uow: UnitOfWork,
    account: FtpAccount,
    plain_password: str,
    settings: Settings | None = None,
) -> None:
    settings = settings or get_settings()
    manager = FtpServiceManager(settings)
    async with uow:
        active = await uow.ftp_accounts.list_active()
    await manager.sync_sftp_user(account, plain_password, active)


async def _rebuild_sftp_accounts(uow: UnitOfWork, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    manager = FtpServiceManager(settings)
    async with uow:
        active = await uow.ftp_accounts.list_active()
    await manager.rebuild_sftp(active)


def build_ftp_account(
    tenant_id: UUID,
    username: str,
    system_username: str,
    plain_password: str,
    home_directory: str,
    quota_mb: int,
    max_files: int,
    upload_bandwidth_kbps: int,
    download_bandwidth_kbps: int,
    settings: Settings,
) -> FtpAccount:
    return FtpAccount(
        tenant_id=tenant_id,
        username=username,
        system_username=system_username,
        password_hash=hash_password(plain_password),
        home_directory=home_directory,
        status=FtpAccountStatus.PENDING,
        quota_mb=quota_mb,
        max_files=max_files,
        upload_bandwidth_kbps=upload_bandwidth_kbps,
        download_bandwidth_kbps=download_bandwidth_kbps,
        uid=settings.pureftpd_virtual_uid,
        gid=settings.pureftpd_virtual_gid,
    )


class CreateFtpAccountHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._settings = settings or get_settings()
        self._provisioner = PureFtpdProvisioner(self._settings)

    async def handle(self, command: CreateFtpAccountCommand) -> tuple[FtpAccount, str]:
        domain = FtpDomainService(self._uow.ftp_accounts)
        username = domain.validate_username(command.username)
        home_directory = domain.validate_directory(command.home_directory)
        quota_mb = domain.validate_quota(command.quota_mb)
        max_files = domain.validate_max_files(command.max_files)
        await domain.ensure_username_available(username, command.tenant_id)

        plain_password = command.password or generate_password()
        system_username = domain.build_system_username(command.tenant_id, username)
        account = build_ftp_account(
            tenant_id=command.tenant_id,
            username=username,
            system_username=system_username,
            plain_password=plain_password,
            home_directory=home_directory,
            quota_mb=quota_mb,
            max_files=max_files,
            upload_bandwidth_kbps=command.upload_bandwidth_kbps,
            download_bandwidth_kbps=command.download_bandwidth_kbps,
            settings=self._settings,
        )

        async with self._uow:
            await self._uow.ftp_accounts.add(account)
            try:
                await self._provisioner.create_user(account, plain_password)
                account.mark_active()
                await self._uow.ftp_accounts.save(account)
            except Exception as exc:
                account.mark_error(str(exc))
                await self._uow.ftp_accounts.save(account)
            await self._uow.commit()

        if account.status == FtpAccountStatus.ACTIVE:
            await _sync_sftp_account(self._uow, account, plain_password, self._settings)
        return account, plain_password


class UpdateFtpAccountHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._provisioner = PureFtpdProvisioner(settings or get_settings())

    async def handle(self, command: UpdateFtpAccountCommand) -> FtpAccount:
        domain = FtpDomainService(self._uow.ftp_accounts)

        async with self._uow:
            account = await self._uow.ftp_accounts.get_by_id_and_tenant(command.account_id, command.tenant_id)
            if not account:
                raise NotFoundError("FTP account not found")

            if command.home_directory is not None:
                account.home_directory = domain.validate_directory(command.home_directory)
            if command.quota_mb is not None:
                account.quota_mb = domain.validate_quota(command.quota_mb)
            if command.max_files is not None:
                account.max_files = domain.validate_max_files(command.max_files)
            if command.upload_bandwidth_kbps is not None:
                account.upload_bandwidth_kbps = max(0, command.upload_bandwidth_kbps)
            if command.download_bandwidth_kbps is not None:
                account.download_bandwidth_kbps = max(0, command.download_bandwidth_kbps)

            if account.status == FtpAccountStatus.ACTIVE:
                try:
                    await self._provisioner.update_user(account)
                    account.mark_active()
                except Exception as exc:
                    account.mark_error(str(exc))

            account.touch()
            await self._uow.ftp_accounts.save(account)
            await self._uow.commit()

        return account


class ChangeFtpPasswordHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._provisioner = PureFtpdProvisioner(settings or get_settings())

    async def handle(self, command: ChangeFtpPasswordCommand) -> tuple[FtpAccount, str]:
        plain_password = command.password or generate_password()

        async with self._uow:
            account = await self._uow.ftp_accounts.get_by_id_and_tenant(command.account_id, command.tenant_id)
            if not account:
                raise NotFoundError("FTP account not found")
            if account.status == FtpAccountStatus.SUSPENDED:
                raise ValidationError("Cannot change password while account is suspended")

            account.password_hash = hash_password(plain_password)
            if account.status == FtpAccountStatus.ACTIVE:
                try:
                    await self._provisioner.change_password(account, plain_password)
                    account.mark_active()
                except Exception as exc:
                    account.mark_error(str(exc))

            account.touch()
            await self._uow.ftp_accounts.save(account)
            await self._uow.commit()

        if account.status == FtpAccountStatus.ACTIVE:
            await _sync_sftp_account(self._uow, account, plain_password, self._settings)
        return account, plain_password


class SetFtpQuotaHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._provisioner = PureFtpdProvisioner(settings or get_settings())

    async def handle(self, command: SetFtpQuotaCommand) -> FtpAccount:
        return await UpdateFtpAccountHandler(self._uow, settings or get_settings()).handle(
            UpdateFtpAccountCommand(
                tenant_id=command.tenant_id,
                account_id=command.account_id,
                home_directory=None,
                quota_mb=command.quota_mb,
                max_files=command.max_files,
                upload_bandwidth_kbps=None,
                download_bandwidth_kbps=None,
            )
        )


class SetFtpDirectoryHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._provisioner = PureFtpdProvisioner(settings or get_settings())

    async def handle(self, command: SetFtpDirectoryCommand) -> FtpAccount:
        return await UpdateFtpAccountHandler(self._uow, settings or get_settings()).handle(
            UpdateFtpAccountCommand(
                tenant_id=command.tenant_id,
                account_id=command.account_id,
                home_directory=command.home_directory,
                quota_mb=None,
                max_files=None,
                upload_bandwidth_kbps=None,
                download_bandwidth_kbps=None,
            )
        )


class SetFtpStatusHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._settings = settings or get_settings()
        self._provisioner = PureFtpdProvisioner(self._settings)

    async def handle(self, command: SetFtpStatusCommand) -> tuple[FtpAccount, str | None]:
        try:
            target_status = FtpAccountStatus(command.status)
        except ValueError as exc:
            raise ValidationError(f"Invalid status: {command.status}") from exc

        generated_password: str | None = None

        async with self._uow:
            account = await self._uow.ftp_accounts.get_by_id_and_tenant(command.account_id, command.tenant_id)
            if not account:
                raise NotFoundError("FTP account not found")

            if target_status == FtpAccountStatus.SUSPENDED:
                if account.status == FtpAccountStatus.ACTIVE:
                    try:
                        await self._provisioner.delete_user(account.system_username)
                    except Exception as exc:
                        account.mark_error(str(exc))
                        await self._uow.ftp_accounts.save(account)
                        await self._uow.commit()
                        return account, None
                account.mark_suspended()
            elif target_status == FtpAccountStatus.ACTIVE:
                generated_password = generate_password()
                account.password_hash = hash_password(generated_password)
                try:
                    exists = await self._provisioner.user_exists(account.system_username)
                    if exists:
                        await self._provisioner.change_password(account, generated_password)
                        await self._provisioner.update_user(account)
                    else:
                        await self._provisioner.create_user(account, generated_password)
                    account.mark_active()
                except Exception as exc:
                    account.mark_error(str(exc))
                    generated_password = None
            else:
                raise ValidationError("Only active or suspended status can be set")

            await self._uow.ftp_accounts.save(account)
            await self._uow.commit()

        manager = FtpServiceManager(self._settings)
        if target_status == FtpAccountStatus.SUSPENDED:
            manager.remove_sftp_password(account.system_username)
            await _rebuild_sftp_accounts(self._uow, self._settings)
        elif target_status == FtpAccountStatus.ACTIVE and generated_password:
            await _sync_sftp_account(self._uow, account, generated_password, self._settings)

        return account, generated_password


class DeleteFtpAccountHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._settings = settings or get_settings()
        self._provisioner = PureFtpdProvisioner(self._settings)

    async def handle(self, command: DeleteFtpAccountCommand) -> None:
        system_username = ""
        async with self._uow:
            account = await self._uow.ftp_accounts.get_by_id_and_tenant(command.account_id, command.tenant_id)
            if not account:
                raise NotFoundError("FTP account not found")
            system_username = account.system_username

            if account.status == FtpAccountStatus.ACTIVE:
                try:
                    await self._provisioner.delete_user(account.system_username)
                except Exception:
                    pass

            await self._uow.ftp_accounts.delete(account.id)
            await self._uow.commit()

        FtpServiceManager(self._settings).remove_sftp_password(system_username)
        await _rebuild_sftp_accounts(self._uow, self._settings)
