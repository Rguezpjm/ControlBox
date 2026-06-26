import asyncio
import logging
import re
from pathlib import Path
from uuid import UUID

from controlbox.config.settings import Settings
from controlbox.modules.ftp.application.site_provisioning import provision_site_ftp_account
from controlbox.modules.joomla.application.commands import ProvisionJoomlaSiteCommand
from controlbox.modules.joomla.domain.entities import (
    JoomlaBackup,
    JoomlaBackupStatus,
    JoomlaSite,
    JoomlaStatus,
)
from controlbox.modules.joomla.infrastructure.database_provisioning import (
    provision_joomla_managed_database,
)
from controlbox.modules.joomla.infrastructure.provision_progress import (
    append_provision_step,
    set_provision_credentials,
)
from controlbox.modules.joomla.infrastructure.provisioner import JoomlaProvisioner
from controlbox.modules.identity.infrastructure.unit_of_work import Database

logger = logging.getLogger("controlbox.joomla")


def _slug_username(raw: str) -> str:
    base = re.sub(r"[^a-z0-9_]+", "_", raw.lower()).strip("_")
    if not base:
        base = "jmftp"
    if not base[0].isalpha():
        base = f"u_{base}"
    return base[:31]


def _ftp_username_from_site(site: JoomlaSite) -> str:
    left = (site.domain.split(".", 1)[0] if site.domain else "") or site.name or "jmftp"
    return _slug_username(left)


def _ftp_home_for_site(settings: Settings, site: JoomlaSite) -> str:
    site_path = (site.site_path or "").replace("\\", "/").strip()
    if not site_path:
        return ""
    try:
        base = Path(settings.sites_base_path).resolve() / str(site.tenant_id)
        full = Path(site_path).resolve()
        rel = full.relative_to(base)
        return str(rel).replace("\\", "/")
    except Exception:
        return site_path.strip("/")


class JoomlaProvisionService:
    def __init__(self, database: Database, settings: Settings) -> None:
        self._database = database
        self._settings = settings
        self._provisioner = JoomlaProvisioner(settings)

    async def _persist_site(self, site: JoomlaSite) -> None:
        async with self._database.unit_of_work() as uow:
            stored = await uow.joomla_sites.get_by_id(site.id)
            if stored is None:
                return
            stored.settings = dict(site.settings)
            stored.status = site.status
            stored.error_message = site.error_message
            stored.managed_database_id = site.managed_database_id
            stored.database_user_id = site.database_user_id
            stored.nginx_container_name = site.nginx_container_name
            stored.php_container_name = site.php_container_name
            stored.disk_used_mb = site.disk_used_mb
            await uow.joomla_sites.save(stored)
            await uow.commit()

    async def _record_step(self, site: JoomlaSite, step: str, message: str) -> None:
        append_provision_step(site, step, message)
        await self._persist_site(site)

    async def provision(self, command: ProvisionJoomlaSiteCommand) -> tuple[str | None, str | None]:
        backup_id: str | None = None
        tenant_id: str | None = None
        async with self._database.unit_of_work() as uow:
            site = await uow.joomla_sites.get_by_id(command.site_id)
            if site is None:
                return None, None

            tenant_id = str(site.tenant_id)
            site.settings["provision_steps"] = []
            site.settings.pop("provision_credentials", None)
            site.status = JoomlaStatus.PROVISIONING
            await uow.joomla_sites.save(site)
            await uow.commit()

        nginx_name = site.nginx_container_name or f"cb-jm-nginx-{site.id.hex[:12]}"
        php_name = site.php_container_name or f"cb-jm-php-{site.id.hex[:12]}"

        try:
            await self._record_step(site, "database", "Creating MySQL database…")
            async with self._database.unit_of_work() as uow:
                stored = await uow.joomla_sites.get_by_id(site.id)
                if stored is None:
                    raise RuntimeError("Joomla site not found during provisioning")
                stored.settings = dict(site.settings)
                db_id, user_id, db_name, db_user, db_password = await provision_joomla_managed_database(
                    uow, self._settings, stored
                )
                site.settings = dict(stored.settings)
            site.managed_database_id = db_id
            site.database_user_id = user_id
            site.settings.update({
                "db_name": db_name,
                "db_user": db_user,
                "db_password_enc": self._provisioner.encrypt_db_password(db_password),
                "db_host": f"{self._settings.mysql_host}:{self._settings.mysql_port}",
            })
            await self._record_step(
                site,
                "database_ready",
                f"Database created: {db_name} · User: {db_user} · Password: {db_password}",
            )

            await self._record_step(
                site,
                "containers",
                "Starting containers, downloading Joomla and running install…",
            )
            await self._provisioner.deploy(
                site=site,
                admin_password=command.admin_password,
                db_name=db_name,
                db_user=db_user,
                db_password=db_password,
                nginx_name=nginx_name,
                php_name=php_name,
            )

            site.mark_running(nginx_name, php_name)
            site.disk_used_mb = self._provisioner.measure_disk_mb(site)
            ftp_username: str | None = None
            ftp_password: str | None = None
            ftp_home: str | None = None

            if bool(site.settings.get("create_ftp_account")):
                await self._record_step(site, "ftp", "Creating FTP account for this Joomla site…")
                ftp_username, ftp_password, ftp_home, ftp_error = await provision_site_ftp_account(
                    self._database,
                    self._settings,
                    tenant_id=site.tenant_id,
                    owner_user_id=site.owner_user_id,
                    username=_ftp_username_from_site(site),
                    home_directory=_ftp_home_for_site(self._settings, site),
                )
                if ftp_username:
                    await self._record_step(site, "ftp_ready", f"FTP account created: {ftp_username}")
                else:
                    await self._record_step(
                        site,
                        "ftp_warn",
                        f"FTP account could not be created: {ftp_error or 'unknown error'}",
                    )

            set_provision_credentials(
                site,
                db_name=db_name,
                db_user=db_user,
                db_password=db_password,
                ftp_username=ftp_username,
                ftp_password=ftp_password,
                ftp_home=ftp_home,
            )
            await self._record_step(site, "complete", "Joomla deployed successfully.")

            async with self._database.unit_of_work() as uow:
                stored = await uow.joomla_sites.get_by_id(site.id)
                if stored:
                    initial_backup = JoomlaBackup(
                        site_id=site.id,
                        tenant_id=site.tenant_id,
                        name="initial-auto-backup",
                        status=JoomlaBackupStatus.PENDING,
                    )
                    await uow.joomla_backups.add(initial_backup)
                    backup_id = str(initial_backup.id)
                    stored.settings = dict(site.settings)
                    stored.status = site.status
                    stored.error_message = None
                    stored.managed_database_id = site.managed_database_id
                    stored.database_user_id = site.database_user_id
                    stored.nginx_container_name = site.nginx_container_name
                    stored.php_container_name = site.php_container_name
                    stored.disk_used_mb = site.disk_used_mb
                    await uow.joomla_sites.save(stored)
                    await uow.commit()
        except Exception as exc:
            logger.exception("Joomla provision failed for %s", site.id)
            site.mark_error(str(exc))
            append_provision_step(site, "error", str(exc))
            await self._persist_site(site)

        return backup_id, tenant_id


def run_provision_site(site_id: str, admin_password: str) -> None:
    from controlbox.config.settings import get_settings
    from controlbox.modules.identity.infrastructure.unit_of_work import Database
    from controlbox.modules.joomla.workers.tasks import run_joomla_backup

    settings = get_settings()
    database = Database(settings)
    service = JoomlaProvisionService(database, settings)
    backup_id, tenant_id = asyncio.run(
        service.provision(
            ProvisionJoomlaSiteCommand(site_id=UUID(site_id), admin_password=admin_password)
        )
    )
    if backup_id and tenant_id:
        run_joomla_backup.delay(backup_id, site_id, tenant_id)


async def run_provision_backup(backup_id: str, site_id: str, tenant_id: str) -> None:
    from controlbox.config.settings import get_settings
    from controlbox.modules.identity.infrastructure.unit_of_work import Database
    from controlbox.modules.joomla.domain.entities import JoomlaBackupStatus, JoomlaStatus

    settings = get_settings()
    database = Database(settings)
    provisioner = JoomlaProvisioner(settings)

    async with database.unit_of_work() as uow:
        site = await uow.joomla_sites.get_by_id_and_tenant(UUID(site_id), UUID(tenant_id))
        backup = await uow.joomla_backups.get_by_id_and_tenant(UUID(backup_id), UUID(tenant_id))
        if not site or not backup:
            return
        site.status = JoomlaStatus.BACKING_UP
        backup.mark_running()
        await uow.joomla_sites.save(site)
        await uow.joomla_backups.save(backup)
        await uow.commit()

    try:
        async with database.unit_of_work() as uow:
            site = await uow.joomla_sites.get_by_id_and_tenant(UUID(site_id), UUID(tenant_id))
            backup = await uow.joomla_backups.get_by_id_and_tenant(UUID(backup_id), UUID(tenant_id))
            if site and backup:
                await provisioner.create_backup(site, backup)
                site.disk_used_mb = provisioner.measure_disk_mb(site)
                site.status = JoomlaStatus.RUNNING
                await uow.joomla_sites.save(site)
                await uow.joomla_backups.save(backup)
                await uow.commit()
    except Exception as exc:
        async with database.unit_of_work() as uow:
            site = await uow.joomla_sites.get_by_id_and_tenant(UUID(site_id), UUID(tenant_id))
            backup = await uow.joomla_backups.get_by_id_and_tenant(UUID(backup_id), UUID(tenant_id))
            if backup:
                backup.mark_failed(str(exc))
                await uow.joomla_backups.save(backup)
            if site:
                site.status = JoomlaStatus.RUNNING
                await uow.joomla_sites.save(site)
            await uow.commit()


async def run_restore_backup(backup_id: str, site_id: str, tenant_id: str) -> None:
    from controlbox.config.settings import get_settings
    from controlbox.modules.identity.infrastructure.unit_of_work import Database
    from controlbox.modules.joomla.domain.entities import JoomlaStatus

    settings = get_settings()
    database = Database(settings)
    provisioner = JoomlaProvisioner(settings)

    async with database.unit_of_work() as uow:
        site = await uow.joomla_sites.get_by_id_and_tenant(UUID(site_id), UUID(tenant_id))
        backup = await uow.joomla_backups.get_by_id_and_tenant(UUID(backup_id), UUID(tenant_id))
        if not site or not backup:
            return
        site.status = JoomlaStatus.RESTORING
        await uow.joomla_sites.save(site)
        await uow.commit()

    try:
        async with database.unit_of_work() as uow:
            site = await uow.joomla_sites.get_by_id_and_tenant(UUID(site_id), UUID(tenant_id))
            backup = await uow.joomla_backups.get_by_id_and_tenant(UUID(backup_id), UUID(tenant_id))
            if site and backup:
                await provisioner.restore_backup(site, backup)
                site.status = JoomlaStatus.RUNNING
                site.disk_used_mb = provisioner.measure_disk_mb(site)
                await uow.joomla_sites.save(site)
                await uow.commit()
    except Exception as exc:
        async with database.unit_of_work() as uow:
            site = await uow.joomla_sites.get_by_id_and_tenant(UUID(site_id), UUID(tenant_id))
            if site:
                site.mark_error(str(exc))
                await uow.joomla_sites.save(site)
                await uow.commit()
