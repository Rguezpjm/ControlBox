import asyncio
import logging
from uuid import UUID

from controlbox.config.settings import Settings
from controlbox.modules.wordpress.application.commands import ProvisionWordPressSiteCommand
from controlbox.modules.wordpress.domain.entities import (
    WordPressBackup,
    WordPressBackupStatus,
    WordPressSite,
    WordPressStatus,
)
from controlbox.modules.wordpress.infrastructure.database_provisioning import (
    provision_wordpress_managed_database,
)
from controlbox.modules.wordpress.infrastructure.provision_progress import (
    append_provision_step,
    set_provision_credentials,
)
from controlbox.modules.wordpress.infrastructure.provisioner import WordPressProvisioner
from controlbox.modules.identity.infrastructure.unit_of_work import Database

logger = logging.getLogger("controlbox.wordpress")


class WordPressProvisionService:
    def __init__(self, database: Database, settings: Settings) -> None:
        self._database = database
        self._settings = settings
        self._provisioner = WordPressProvisioner(settings)

    async def _persist_site(self, site: WordPressSite) -> None:
        async with self._database.unit_of_work() as uow:
            stored = await uow.wordpress_sites.get_by_id(site.id)
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
            await uow.wordpress_sites.save(stored)
            await uow.commit()

    async def _record_step(self, site: WordPressSite, step: str, message: str) -> None:
        append_provision_step(site, step, message)
        await self._persist_site(site)

    async def provision(self, command: ProvisionWordPressSiteCommand) -> tuple[str | None, str | None]:
        backup_id: str | None = None
        tenant_id: str | None = None
        async with self._database.unit_of_work() as uow:
            site = await uow.wordpress_sites.get_by_id(command.site_id)
            if site is None:
                return None, None

            tenant_id = str(site.tenant_id)
            site.settings["provision_steps"] = []
            site.settings.pop("provision_credentials", None)
            site.status = WordPressStatus.PROVISIONING
            await uow.wordpress_sites.save(site)
            await uow.commit()

        nginx_name = site.nginx_container_name or f"cb-wp-nginx-{site.id.hex[:12]}"
        php_name = site.php_container_name or f"cb-wp-php-{site.id.hex[:12]}"

        try:
            await self._record_step(site, "database", "Creating MySQL database…")
            async with self._database.unit_of_work() as uow:
                stored = await uow.wordpress_sites.get_by_id(site.id)
                if stored is None:
                    raise RuntimeError("WordPress site not found during provisioning")
                stored.settings = dict(site.settings)
                db_id, user_id, db_name, db_user, db_password = await provision_wordpress_managed_database(
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
                "Starting containers, downloading WordPress and running install…",
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
            set_provision_credentials(
                site,
                db_name=db_name,
                db_user=db_user,
                db_password=db_password,
            )
            await self._record_step(site, "complete", "WordPress deployed successfully.")

            async with self._database.unit_of_work() as uow:
                stored = await uow.wordpress_sites.get_by_id(site.id)
                if stored:
                    initial_backup = WordPressBackup(
                        site_id=site.id,
                        tenant_id=site.tenant_id,
                        name="initial-auto-backup",
                        status=WordPressBackupStatus.PENDING,
                    )
                    await uow.wordpress_backups.add(initial_backup)
                    backup_id = str(initial_backup.id)
                    stored.settings = dict(site.settings)
                    stored.status = site.status
                    stored.error_message = None
                    stored.managed_database_id = site.managed_database_id
                    stored.database_user_id = site.database_user_id
                    stored.nginx_container_name = site.nginx_container_name
                    stored.php_container_name = site.php_container_name
                    stored.disk_used_mb = site.disk_used_mb
                    await uow.wordpress_sites.save(stored)
                    await uow.commit()
        except Exception as exc:
            logger.exception("WordPress provision failed for %s", site.id)
            site.mark_error(str(exc))
            append_provision_step(site, "error", str(exc))
            await self._persist_site(site)

        return backup_id, tenant_id


def run_provision_site(site_id: str, admin_password: str) -> None:
    from controlbox.config.settings import get_settings
    from controlbox.modules.identity.infrastructure.unit_of_work import Database
    from controlbox.modules.wordpress.workers.tasks import run_wordpress_backup

    settings = get_settings()
    database = Database(settings)
    service = WordPressProvisionService(database, settings)
    backup_id, tenant_id = asyncio.run(
        service.provision(
            ProvisionWordPressSiteCommand(site_id=UUID(site_id), admin_password=admin_password)
        )
    )
    if backup_id and tenant_id:
        run_wordpress_backup.delay(backup_id, site_id, tenant_id)


async def run_provision_backup(backup_id: str, site_id: str, tenant_id: str) -> None:
    from controlbox.config.settings import get_settings
    from controlbox.modules.identity.infrastructure.unit_of_work import Database
    from controlbox.modules.wordpress.domain.entities import WordPressBackupStatus, WordPressStatus

    settings = get_settings()
    database = Database(settings)
    provisioner = WordPressProvisioner(settings)

    async with database.unit_of_work() as uow:
        site = await uow.wordpress_sites.get_by_id_and_tenant(UUID(site_id), UUID(tenant_id))
        backup = await uow.wordpress_backups.get_by_id_and_tenant(UUID(backup_id), UUID(tenant_id))
        if not site or not backup:
            return
        site.status = WordPressStatus.BACKING_UP
        backup.mark_running()
        await uow.wordpress_sites.save(site)
        await uow.wordpress_backups.save(backup)
        await uow.commit()

    try:
        async with database.unit_of_work() as uow:
            site = await uow.wordpress_sites.get_by_id_and_tenant(UUID(site_id), UUID(tenant_id))
            backup = await uow.wordpress_backups.get_by_id_and_tenant(UUID(backup_id), UUID(tenant_id))
            if site and backup:
                await provisioner.create_backup(site, backup)
                site.disk_used_mb = provisioner.measure_disk_mb(site)
                site.status = WordPressStatus.RUNNING
                await uow.wordpress_sites.save(site)
                await uow.wordpress_backups.save(backup)
                await uow.commit()
    except Exception as exc:
        async with database.unit_of_work() as uow:
            site = await uow.wordpress_sites.get_by_id_and_tenant(UUID(site_id), UUID(tenant_id))
            backup = await uow.wordpress_backups.get_by_id_and_tenant(UUID(backup_id), UUID(tenant_id))
            if backup:
                backup.mark_failed(str(exc))
                await uow.wordpress_backups.save(backup)
            if site:
                site.status = WordPressStatus.RUNNING
                await uow.wordpress_sites.save(site)
            await uow.commit()


async def run_restore_backup(backup_id: str, site_id: str, tenant_id: str) -> None:
    from controlbox.config.settings import get_settings
    from controlbox.modules.identity.infrastructure.unit_of_work import Database
    from controlbox.modules.wordpress.domain.entities import WordPressStatus

    settings = get_settings()
    database = Database(settings)
    provisioner = WordPressProvisioner(settings)

    async with database.unit_of_work() as uow:
        site = await uow.wordpress_sites.get_by_id_and_tenant(UUID(site_id), UUID(tenant_id))
        backup = await uow.wordpress_backups.get_by_id_and_tenant(UUID(backup_id), UUID(tenant_id))
        if not site or not backup:
            return
        site.status = WordPressStatus.RESTORING
        await uow.wordpress_sites.save(site)
        await uow.commit()

    try:
        async with database.unit_of_work() as uow:
            site = await uow.wordpress_sites.get_by_id_and_tenant(UUID(site_id), UUID(tenant_id))
            backup = await uow.wordpress_backups.get_by_id_and_tenant(UUID(backup_id), UUID(tenant_id))
            if site and backup:
                await provisioner.restore_backup(site, backup)
                site.status = WordPressStatus.RUNNING
                site.disk_used_mb = provisioner.measure_disk_mb(site)
                await uow.wordpress_sites.save(site)
                await uow.commit()
    except Exception as exc:
        async with database.unit_of_work() as uow:
            site = await uow.wordpress_sites.get_by_id_and_tenant(UUID(site_id), UUID(tenant_id))
            if site:
                site.mark_error(str(exc))
                await uow.wordpress_sites.save(site)
                await uow.commit()
