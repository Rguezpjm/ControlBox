import asyncio
import logging
from uuid import UUID

from controlbox.config.settings import Settings
from controlbox.modules.identity.infrastructure.unit_of_work import Database
from controlbox.modules.staging_sites.application.commands import (
    ProvisionStagingSiteCommand,
    RunStagingSyncCommand,
)
from controlbox.modules.staging_sites.domain.entities import StagingStatus, SyncDirection, SyncType
from controlbox.modules.staging_sites.infrastructure.provisioner import StagingProvisioner

logger = logging.getLogger("controlbox.staging")


class StagingProvisionService:
    def __init__(self, database: Database, settings: Settings) -> None:
        self._database = database
        self._settings = settings
        self._provisioner = StagingProvisioner(settings)

    async def provision(self, command: ProvisionStagingSiteCommand) -> None:
        async with self._database.unit_of_work() as uow:
            staging = await uow.staging_sites.get_by_id(command.staging_id)
            if staging is None:
                return
            staging.status = StagingStatus.PROVISIONING
            await uow.staging_sites.save(staging)
            await uow.commit()

        try:
            async with self._database.unit_of_work() as uow:
                staging = await uow.staging_sites.get_by_id(command.staging_id)
                if staging is None:
                    return
                await self._provisioner.provision(staging, uow)
                staging.mark_running()
                await uow.staging_sites.save(staging)
                await uow.commit()
        except Exception as exc:
            logger.exception("Staging provision failed for %s", command.staging_id)
            async with self._database.unit_of_work() as uow:
                staging = await uow.staging_sites.get_by_id(command.staging_id)
                if staging:
                    staging.mark_error(str(exc))
                    await uow.staging_sites.save(staging)
                    await uow.commit()

    async def sync(self, command: RunStagingSyncCommand) -> None:
        direction = SyncDirection(command.direction)
        sync_type = SyncType(command.sync_type)
        to_production = direction == SyncDirection.TO_PRODUCTION

        async with self._database.unit_of_work() as uow:
            staging = await uow.staging_sites.get_by_id(command.staging_id)
            if staging is None:
                return
            staging.mark_syncing(direction, sync_type)
            await uow.staging_sites.save(staging)
            await uow.commit()

        try:
            async with self._database.unit_of_work() as uow:
                staging = await uow.staging_sites.get_by_id(command.staging_id)
                if staging is None:
                    return
                await self._provisioner.sync(staging, uow, sync_type, to_production)
                staging.mark_sync_complete(sync_type, direction)
                await uow.staging_sites.save(staging)
                await uow.commit()
        except Exception as exc:
            logger.exception("Staging sync failed for %s", command.staging_id)
            async with self._database.unit_of_work() as uow:
                staging = await uow.staging_sites.get_by_id(command.staging_id)
                if staging:
                    staging.mark_error(str(exc))
                    await uow.staging_sites.save(staging)
                    await uow.commit()

    async def delete(self, staging_id: UUID) -> None:
        async with self._database.unit_of_work() as uow:
            staging = await uow.staging_sites.get_by_id(staging_id)
            if staging is None:
                return
            try:
                await self._provisioner.destroy(staging)
            except Exception as exc:
                logger.warning("Staging destroy error: %s", exc)

        async with self._database.unit_of_work() as uow:
            staging = await uow.staging_sites.get_by_id(staging_id)
            if staging:
                await uow.staging_sites.delete(staging_id)
                await uow.commit()


def run_provision_staging(staging_id: str) -> None:
    from controlbox.config.settings import get_settings

    settings = get_settings()
    database = Database(settings)
    service = StagingProvisionService(database, settings)
    asyncio.run(service.provision(ProvisionStagingSiteCommand(staging_id=UUID(staging_id))))


def run_sync_staging(staging_id: str, sync_type: str, direction: str) -> None:
    from controlbox.config.settings import get_settings

    settings = get_settings()
    database = Database(settings)
    service = StagingProvisionService(database, settings)
    asyncio.run(
        service.sync(
            RunStagingSyncCommand(
                staging_id=UUID(staging_id),
                sync_type=sync_type,
                direction=direction,
            )
        )
    )


def run_delete_staging(staging_id: str) -> None:
    from controlbox.config.settings import get_settings

    settings = get_settings()
    database = Database(settings)
    service = StagingProvisionService(database, settings)
    asyncio.run(service.delete(UUID(staging_id)))
