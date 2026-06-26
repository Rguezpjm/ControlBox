from controlbox.shared.infrastructure.celery.app import celery_app


@celery_app.task(name="joomla.provision_site", bind=True, max_retries=2)
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
