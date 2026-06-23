from controlbox.modules.ftp.domain.entities import FtpAccount, FtpAccountStatus
from controlbox.modules.ftp.infrastructure.models import FtpAccountModel


def to_ftp_account(model: FtpAccountModel) -> FtpAccount:
    return FtpAccount(
        id=model.id,
        tenant_id=model.tenant_id,
        owner_user_id=model.owner_user_id,
        username=model.username,
        system_username=model.system_username,
        password_hash=model.password_hash,
        home_directory=model.home_directory,
        status=FtpAccountStatus(model.status),
        quota_mb=model.quota_mb,
        max_files=model.max_files,
        upload_bandwidth_kbps=model.upload_bandwidth_kbps,
        download_bandwidth_kbps=model.download_bandwidth_kbps,
        uid=model.uid,
        gid=model.gid,
        last_login_at=model.last_login_at,
        error_message=model.error_message,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
