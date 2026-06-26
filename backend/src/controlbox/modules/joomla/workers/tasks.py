import asyncio
from uuid import UUID

from controlbox.shared.infrastructure.celery.app import celery_app


def _joomla_provision_on_failure(self, exc, task_id, args, kwargs, einfo):
    from controlbox.config.settings import get_settings
    from controlbox.modules.identity.infrastructure.unit_of_work import Database

    site_id = args[0] if args else None
    if not site_id:
        return

    settings = get_settings()
    db = Database(settings)

    async def _mark_error():
        async with db.unit_of_work() as uow:
            site = await uow.joomla_sites.get_by_id(UUID(site_id))
            if site:
                site.mark_error(str(exc))
                await uow.joomla_sites.save(site)
                await uow.commit()

    asyncio.run(_mark_error())


@celery_app.task(name="joomla.provision_site", bind=True, max_retries=2, on_failure=_joomla_provision_on_failure)
def provision_joomla_site(self, site_id: str, admin_password: str) -> None:
    from controlbox.modules.joomla.application.provision_service import run_provision_site

    try:
        run_provision_site(site_id, admin_password)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="joomla.run_backup")
def run_joomla_backup(backup_id: str, site_id: str, tenant_id: str) -> None:
    import asyncio

    from controlbox.modules.joomla.application.provision_service import run_provision_backup

    asyncio.run(run_provision_backup(backup_id, site_id, tenant_id))


@celery_app.task(name="joomla.restore_backup")
def restore_joomla_backup(backup_id: str, site_id: str, tenant_id: str) -> None:
    import asyncio

    from controlbox.modules.joomla.application.provision_service import run_restore_backup

    asyncio.run(run_restore_backup(backup_id, site_id, tenant_id))
