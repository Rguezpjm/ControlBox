from controlbox.shared.infrastructure.celery.app import celery_app


@celery_app.task(name="staging.provision", bind=True, max_retries=2)
def provision_staging_site(self, staging_id: str) -> None:
    from controlbox.modules.staging_sites.application.provision_service import run_provision_staging

    try:
        run_provision_staging(staging_id)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="staging.sync", bind=True, max_retries=1)
def sync_staging_site(self, staging_id: str, sync_type: str, direction: str) -> None:
    from controlbox.modules.staging_sites.application.provision_service import run_sync_staging

    try:
        run_sync_staging(staging_id, sync_type, direction)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=15)


@celery_app.task(name="staging.delete")
def delete_staging_site(staging_id: str) -> None:
    from controlbox.modules.staging_sites.application.provision_service import run_delete_staging

    run_delete_staging(staging_id)


@celery_app.task(name="staging.restart")
def restart_staging_site(staging_id: str) -> None:
    import asyncio
    from uuid import UUID

    from controlbox.config.settings import get_settings
    from controlbox.modules.identity.infrastructure.unit_of_work import Database
    from controlbox.modules.staging_sites.infrastructure.provisioner import StagingProvisioner

    settings = get_settings()
    database = Database(settings)
    provisioner = StagingProvisioner(settings)

    async def _restart() -> None:
        async with database.unit_of_work() as uow:
            staging = await uow.staging_sites.get_by_id(UUID(staging_id))
            if staging:
                await provisioner.restart(staging)

    asyncio.run(_restart())
