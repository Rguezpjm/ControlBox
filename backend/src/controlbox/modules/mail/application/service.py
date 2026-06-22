import re
from uuid import UUID

from controlbox.config.settings import Settings
from controlbox.modules.databases.infrastructure.engine_adapters import generate_password, hash_password
from controlbox.modules.mail.domain.entities import MailAccount, MailAccountStatus, TenantMailService, TenantMailStatus
from controlbox.modules.mail.infrastructure.connector import test_mail_connection
from controlbox.modules.supabase.infrastructure.crypto import SecretEncryptor
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import ConflictError, ForbiddenError, NotFoundError, ValidationError, utc_now

DOMAIN_PATTERN = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")
LOCAL_PART_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}[a-z0-9]$|^[a-z0-9]$")


class MailApplicationService:
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._settings = settings
        self._crypto = SecretEncryptor(settings)

    def _normalize_domain(self, domain: str) -> str:
        normalized = domain.strip().lower()
        if not DOMAIN_PATTERN.match(normalized):
            raise ValidationError("Invalid mail domain format")
        return normalized

    def _normalize_local_part(self, local_part: str) -> str:
        cleaned = local_part.strip().lower()
        if not LOCAL_PART_PATTERN.match(cleaned):
            raise ValidationError("Invalid mailbox name (use letters, numbers, dots, dashes)")
        return cleaned

    async def get_service(self, tenant_id: UUID) -> TenantMailService | None:
        return await self._uow.tenant_mail_services.get_by_tenant(tenant_id)

    async def create_service(self, tenant_id: UUID, name: str, mail_domain: str) -> TenantMailService:
        existing = await self._uow.tenant_mail_services.get_by_tenant(tenant_id)
        if existing:
            raise ConflictError("A tenant email service already exists for this organization")

        domain = self._normalize_domain(mail_domain)
        service = TenantMailService(
            tenant_id=tenant_id,
            name=name.strip(),
            mail_domain=domain,
            status=TenantMailStatus.PENDING,
        )
        await self._uow.tenant_mail_services.add(service)
        await self._uow.commit()
        return service

    async def update_service(
        self,
        tenant_id: UUID,
        *,
        name: str | None = None,
        imap_host: str | None = None,
        imap_port: int | None = None,
        imap_use_ssl: bool | None = None,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        smtp_use_ssl: bool | None = None,
        smtp_use_tls: bool | None = None,
        admin_username: str | None = None,
        admin_password: str | None = None,
        default_quota_mb: int | None = None,
        total_quota_mb: int | None = None,
        webmail_url: str | None = None,
    ) -> TenantMailService:
        service = await self._require_service(tenant_id)
        if service.status == TenantMailStatus.ACTIVE:
            raise ValidationError("Disconnect the mail service before changing server settings")

        if name is not None:
            service.name = name.strip()
        if imap_host is not None:
            service.imap_host = imap_host.strip()
        if imap_port is not None:
            service.imap_port = imap_port
        if imap_use_ssl is not None:
            service.imap_use_ssl = imap_use_ssl
        if smtp_host is not None:
            service.smtp_host = smtp_host.strip()
        if smtp_port is not None:
            service.smtp_port = smtp_port
        if smtp_use_ssl is not None:
            service.smtp_use_ssl = smtp_use_ssl
        if smtp_use_tls is not None:
            service.smtp_use_tls = smtp_use_tls
        if admin_username is not None:
            service.admin_username = admin_username.strip()
        if admin_password:
            service.admin_password_enc = self._crypto.encrypt(admin_password)
        if default_quota_mb is not None:
            service.default_quota_mb = max(100, default_quota_mb)
        if total_quota_mb is not None:
            service.total_quota_mb = max(service.default_quota_mb, total_quota_mb)
        if webmail_url is not None:
            service.webmail_url = webmail_url.strip() or None

        service.mark_configuring()
        await self._uow.tenant_mail_services.save(service)
        await self._uow.commit()
        return service

    async def verify_service(self, tenant_id: UUID, admin_password: str | None = None) -> TenantMailService:
        service = await self._require_service(tenant_id)
        password = admin_password
        if not password:
            if not service.admin_password_enc:
                raise ValidationError("Admin password is required to verify the connection")
            password = self._crypto.decrypt(service.admin_password_enc)
        elif not service.admin_password_enc:
            service.admin_password_enc = self._crypto.encrypt(admin_password)

        ok, message = await test_mail_connection(
            imap_host=service.imap_host,
            imap_port=service.imap_port,
            imap_use_ssl=service.imap_use_ssl,
            smtp_host=service.smtp_host,
            smtp_port=service.smtp_port,
            smtp_use_ssl=service.smtp_use_ssl,
            smtp_use_tls=service.smtp_use_tls,
            username=service.admin_username,
            password=password,
        )
        if not ok:
            service.mark_error(message)
            await self._uow.tenant_mail_services.save(service)
            await self._uow.commit()
            raise ValidationError(message)

        service.mark_active()
        service.connection_verified_at = utc_now()
        await self._uow.tenant_mail_services.save(service)
        await self._uow.commit()
        return service

    async def delete_service(self, tenant_id: UUID) -> None:
        service = await self._require_service(tenant_id)
        accounts = await self._uow.mail_accounts.list_by_service(service.id, tenant_id)
        if accounts:
            raise ValidationError("Delete all mailboxes before removing the tenant email service")
        await self._uow.tenant_mail_services.delete(service.id)
        await self._uow.commit()

    async def get_overview(self, tenant_id: UUID) -> dict:
        service = await self._uow.tenant_mail_services.get_by_tenant(tenant_id)
        if not service:
            return {
                "configured": False,
                "accounts_count": 0,
                "total_quota_mb": 0,
                "total_used_mb": 0,
            }
        _, used_mb, count = await self._uow.mail_accounts.sum_quota_and_usage(service.id)
        return {
            "configured": True,
            "accounts_count": count,
            "total_quota_mb": service.total_quota_mb,
            "total_used_mb": used_mb,
        }

    async def list_accounts(self, tenant_id: UUID) -> list[MailAccount]:
        service = await self._require_active_service(tenant_id)
        return await self._uow.mail_accounts.list_by_service(service.id, tenant_id)

    async def create_account(
        self,
        tenant_id: UUID,
        *,
        local_part: str,
        display_name: str,
        password: str | None,
        quota_mb: int | None,
    ) -> tuple[MailAccount, str]:
        service = await self._require_active_service(tenant_id)
        part = self._normalize_local_part(local_part)
        existing = await self._uow.mail_accounts.get_by_local_part(service.id, part)
        if existing:
            raise ConflictError(f"Mailbox '{part}@{service.mail_domain}' already exists")

        assigned_quota = quota_mb if quota_mb is not None else service.default_quota_mb
        total_quota, _, count = await self._uow.mail_accounts.sum_quota_and_usage(service.id)
        if total_quota + assigned_quota > service.total_quota_mb:
            raise ValidationError("Tenant mail quota exceeded. Increase total quota or remove mailboxes.")

        plain_password = password or generate_password()
        account = MailAccount(
            tenant_id=tenant_id,
            mail_service_id=service.id,
            local_part=part,
            email_address=f"{part}@{service.mail_domain}",
            display_name=display_name.strip() or part,
            password_hash=hash_password(plain_password),
            quota_mb=assigned_quota,
            status=MailAccountStatus.ACTIVE,
        )
        await self._uow.mail_accounts.add(account)
        await self._uow.commit()
        return account, plain_password

    async def update_account(
        self,
        tenant_id: UUID,
        account_id: UUID,
        *,
        display_name: str | None = None,
        quota_mb: int | None = None,
        status: str | None = None,
        forwarding_to: str | None = None,
    ) -> MailAccount:
        service = await self._require_active_service(tenant_id)
        account = await self._require_account(tenant_id, account_id)
        if account.mail_service_id != service.id:
            raise NotFoundError("Mailbox not found")

        if display_name is not None:
            account.display_name = display_name.strip()
        if quota_mb is not None:
            other_quota, _, _ = await self._uow.mail_accounts.sum_quota_and_usage(service.id)
            new_total = other_quota - account.quota_mb + quota_mb
            if new_total > service.total_quota_mb:
                raise ValidationError("Tenant mail quota exceeded")
            account.quota_mb = max(100, quota_mb)
        if status is not None:
            if status == "suspended":
                account.mark_suspended()
            elif status == "active":
                account.mark_active()
            else:
                raise ValidationError("Invalid mailbox status")
        if forwarding_to is not None:
            account.forwarding_to = forwarding_to.strip() or None

        await self._uow.mail_accounts.save(account)
        await self._uow.commit()
        return account

    async def delete_account(self, tenant_id: UUID, account_id: UUID) -> None:
        service = await self._require_active_service(tenant_id)
        account = await self._require_account(tenant_id, account_id)
        if account.mail_service_id != service.id:
            raise NotFoundError("Mailbox not found")
        await self._uow.mail_accounts.delete(account_id)
        await self._uow.commit()

    async def dns_checklist(self, tenant_id: UUID) -> list[dict]:
        service = await self._require_service(tenant_id)
        domain = service.mail_domain
        return [
            {
                "type": "MX",
                "name": domain,
                "value": f"mail.{domain} (priority 10)",
                "purpose": "Routes incoming mail to your mail server",
            },
            {
                "type": "TXT",
                "name": domain,
                "value": f"v=spf1 mx a:mail.{domain} ~all",
                "purpose": "SPF — authorizes senders for your domain",
            },
            {
                "type": "TXT",
                "name": f"_dmarc.{domain}",
                "value": f"v=DMARC1; p=none; rua=mailto:dmarc@{domain}",
                "purpose": "DMARC — email authentication policy",
            },
            {
                "type": "CNAME",
                "name": f"autodiscover.{domain}",
                "value": f"mail.{domain}",
                "purpose": "Autodiscover for mail clients (Outlook-style)",
            },
        ]

    async def _require_service(self, tenant_id: UUID) -> TenantMailService:
        service = await self._uow.tenant_mail_services.get_by_tenant(tenant_id)
        if not service:
            raise NotFoundError("Tenant email service not configured")
        return service

    async def _require_active_service(self, tenant_id: UUID) -> TenantMailService:
        service = await self._require_service(tenant_id)
        if service.status != TenantMailStatus.ACTIVE:
            raise ForbiddenError("Complete mail server configuration and verify the connection first")
        return service

    async def _require_account(self, tenant_id: UUID, account_id: UUID) -> MailAccount:
        account = await self._uow.mail_accounts.get_by_id(account_id, tenant_id)
        if not account:
            raise NotFoundError("Mailbox not found")
        return account
