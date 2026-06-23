from controlbox.config.settings import get_settings
from controlbox.modules.ftp.application.queries import (
    FtpAccountResponse,
    FtpLogResponse,
    FtpServiceStatusResponse,
    GetFtpAccountQuery,
    ListFtpAccountsQuery,
    ListFtpLogsQuery,
)
from controlbox.modules.ftp.infrastructure.provisioner import FtpLogReader
from controlbox.modules.ftp.infrastructure.service_manager import FtpServiceManager
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import NotFoundError


def to_account_response(account) -> FtpAccountResponse:
    return FtpAccountResponse(
        id=account.id,
        tenant_id=account.tenant_id,
        username=account.username,
        system_username=account.system_username,
        home_directory=account.home_directory,
        status=account.status.value,
        quota_mb=account.quota_mb,
        max_files=account.max_files,
        upload_bandwidth_kbps=account.upload_bandwidth_kbps,
        download_bandwidth_kbps=account.download_bandwidth_kbps,
        last_login_at=account.last_login_at,
        error_message=account.error_message,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


class ListFtpAccountsHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListFtpAccountsQuery) -> list[FtpAccountResponse]:
        async with self._uow:
            accounts = await self._uow.ftp_accounts.list_by_tenant(query.tenant_id)
        if not query.can_manage_all:
            accounts = [
                account for account in accounts
                if account.owner_user_id is not None and account.owner_user_id == query.requester_user_id
            ]
        return [to_account_response(account) for account in accounts]


class GetFtpAccountHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: GetFtpAccountQuery) -> FtpAccountResponse:
        async with self._uow:
            account = await self._uow.ftp_accounts.get_by_id_and_tenant(query.account_id, query.tenant_id)
            if not account:
                raise NotFoundError("FTP account not found")
            if not query.can_manage_all and account.owner_user_id != query.requester_user_id:
                raise NotFoundError("FTP account not found")
        return to_account_response(account)


class ListFtpLogsHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow
        self._settings = get_settings()
        self._reader = FtpLogReader(self._settings)

    async def handle(self, query: ListFtpLogsQuery) -> list[FtpLogResponse]:
        async with self._uow:
            accounts = await self._uow.ftp_accounts.list_by_tenant(query.tenant_id)
            if not query.can_manage_all:
                accounts = [
                    account for account in accounts
                    if account.owner_user_id is not None and account.owner_user_id == query.requester_user_id
                ]
            if query.account_id:
                account = await self._uow.ftp_accounts.get_by_id_and_tenant(query.account_id, query.tenant_id)
                if not account:
                    raise NotFoundError("FTP account not found")
                if not query.can_manage_all and account.owner_user_id != query.requester_user_id:
                    raise NotFoundError("FTP account not found")
                accounts = [account]

        system_usernames = {account.system_username for account in accounts}
        username_map = {account.system_username: account.username for account in accounts}
        filter_username = None
        if query.account_id and accounts:
            filter_username = accounts[0].system_username

        entries = self._reader.read_logs(
            system_usernames=system_usernames,
            username_map=username_map,
            limit=min(query.limit, 500),
            account_filter=filter_username,
        )

        return [
            FtpLogResponse(
                timestamp=entry.timestamp,
                username=entry.username,
                action=entry.action,
                path=entry.path,
                bytes_transferred=entry.bytes_transferred,
                ip_address=entry.ip_address,
                status=entry.status,
            )
            for entry in entries
        ]


class GetFtpServiceStatusHandler:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._manager = FtpServiceManager(self._settings)

    async def handle(self) -> FtpServiceStatusResponse:
        config = await self._manager.get_config()
        return FtpServiceStatusResponse(
            enabled=config.enabled,
            status=config.status,
            host=config.host,
            port=config.port,
            protocol=config.protocol,
            passive_port_min=config.passive_port_min,
            passive_port_max=config.passive_port_max,
            public_host=config.public_host,
            running=config.running,
            can_manage=config.can_manage,
            message=config.message,
        )
