from controlbox.modules.mail.domain.entities import MailAccount, MailAccountStatus, TenantMailService, TenantMailStatus
from controlbox.modules.mail.infrastructure.models import MailAccountModel, TenantMailServiceModel


def service_to_entity(model: TenantMailServiceModel) -> TenantMailService:
    return TenantMailService(
        id=model.id,
        tenant_id=model.tenant_id,
        name=model.name,
        mail_domain=model.mail_domain,
        status=TenantMailStatus(model.status),
        imap_host=model.imap_host,
        imap_port=model.imap_port,
        imap_use_ssl=model.imap_use_ssl,
        smtp_host=model.smtp_host,
        smtp_port=model.smtp_port,
        smtp_use_ssl=model.smtp_use_ssl,
        smtp_use_tls=model.smtp_use_tls,
        admin_username=model.admin_username,
        admin_password_enc=model.admin_password_enc,
        default_quota_mb=model.default_quota_mb,
        total_quota_mb=model.total_quota_mb,
        webmail_url=model.webmail_url,
        connection_verified_at=model.connection_verified_at,
        error_message=model.error_message,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def service_to_model(entity: TenantMailService) -> TenantMailServiceModel:
    return TenantMailServiceModel(
        id=entity.id,
        tenant_id=entity.tenant_id,
        name=entity.name,
        mail_domain=entity.mail_domain,
        status=entity.status.value,
        imap_host=entity.imap_host,
        imap_port=entity.imap_port,
        imap_use_ssl=entity.imap_use_ssl,
        smtp_host=entity.smtp_host,
        smtp_port=entity.smtp_port,
        smtp_use_ssl=entity.smtp_use_ssl,
        smtp_use_tls=entity.smtp_use_tls,
        admin_username=entity.admin_username,
        admin_password_enc=entity.admin_password_enc,
        default_quota_mb=entity.default_quota_mb,
        total_quota_mb=entity.total_quota_mb,
        webmail_url=entity.webmail_url,
        connection_verified_at=entity.connection_verified_at,
        error_message=entity.error_message,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def account_to_entity(model: MailAccountModel) -> MailAccount:
    return MailAccount(
        id=model.id,
        tenant_id=model.tenant_id,
        mail_service_id=model.mail_service_id,
        local_part=model.local_part,
        email_address=model.email_address,
        display_name=model.display_name,
        password_hash=model.password_hash,
        status=MailAccountStatus(model.status),
        quota_mb=model.quota_mb,
        used_mb=model.used_mb,
        forwarding_to=model.forwarding_to,
        error_message=model.error_message,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def account_to_model(entity: MailAccount) -> MailAccountModel:
    return MailAccountModel(
        id=entity.id,
        tenant_id=entity.tenant_id,
        mail_service_id=entity.mail_service_id,
        local_part=entity.local_part,
        email_address=entity.email_address,
        display_name=entity.display_name,
        password_hash=entity.password_hash,
        status=entity.status.value,
        quota_mb=entity.quota_mb,
        used_mb=entity.used_mb,
        forwarding_to=entity.forwarding_to,
        error_message=entity.error_message,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )
