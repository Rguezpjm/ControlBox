from controlbox.config.settings import Settings, get_settings
from controlbox.modules.backups.application.commands import (
    CreateBackupDestinationCommand,
    CreateBackupJobCommand,
    CreateBackupScheduleCommand,
    DeleteBackupDestinationCommand,
    DeleteBackupJobCommand,
    DeleteBackupScheduleCommand,
    PauseBackupScheduleCommand,
    ResumeBackupScheduleCommand,
    RunBackupScheduleCommand,
    RestoreBackupJobCommand,
    UpdateBackupDestinationCommand,
    UpdateBackupScheduleCommand,
)
from controlbox.modules.backups.domain.entities import (
    BackupDestination,
    BackupSchedule,
    BackupTriggerType,
)
from controlbox.modules.backups.domain.services import BackupDomainService
from controlbox.modules.backups.infrastructure.engine import BackupEngine, compute_next_run
from controlbox.modules.backups.infrastructure.storage import StorageAdapterFactory
from controlbox.modules.supabase.infrastructure.crypto import SecretEncryptor
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import NotFoundError, ValidationError, utc_now


class CreateBackupDestinationHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._settings = settings or get_settings()
        self._encryptor = SecretEncryptor(self._settings)

    async def handle(self, command: CreateBackupDestinationCommand) -> BackupDestination:
        domain = BackupDomainService(self._uow.backup_destinations)
        name = domain.validate_name(command.name)
        dest_type = domain.validate_destination_type(command.destination_type)
        await domain.ensure_destination_name_available(name, command.tenant_id)

        if dest_type.value != "local" and (not command.access_key or not command.secret_key):
            raise ValidationError("Access key and secret key required for remote destinations")

        destination = BackupDestination(
            tenant_id=command.tenant_id,
            name=name,
            destination_type=dest_type,
            bucket=command.bucket,
            endpoint=command.endpoint,
            region=command.region,
            prefix=command.prefix,
            local_path=command.local_path or self._settings.backups_base_path,
            access_key_encrypted=self._encryptor.encrypt(command.access_key) if command.access_key else "",
            secret_key_encrypted=self._encryptor.encrypt(command.secret_key) if command.secret_key else "",
            is_default=command.is_default,
        )

        async with self._uow:
            if command.is_default:
                for existing in await self._uow.backup_destinations.list_by_tenant(command.tenant_id):
                    if existing.is_default:
                        existing.is_default = False
                        await self._uow.backup_destinations.save(existing)

            await self._uow.backup_destinations.add(destination)
            await self._uow.commit()

        return destination


class UpdateBackupDestinationHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._encryptor = SecretEncryptor(settings or get_settings())

    async def handle(self, command: UpdateBackupDestinationCommand) -> BackupDestination:
        async with self._uow:
            destination = await self._uow.backup_destinations.get_by_id_and_tenant(
                command.destination_id, command.tenant_id
            )
            if not destination:
                raise NotFoundError("Destination not found")

            if command.name is not None:
                destination.name = BackupDomainService(self._uow.backup_destinations).validate_name(command.name)
            if command.bucket is not None:
                destination.bucket = command.bucket
            if command.endpoint is not None:
                destination.endpoint = command.endpoint
            if command.region is not None:
                destination.region = command.region
            if command.prefix is not None:
                destination.prefix = command.prefix
            if command.local_path is not None:
                destination.local_path = command.local_path
            if command.access_key:
                destination.access_key_encrypted = self._encryptor.encrypt(command.access_key)
            if command.secret_key:
                destination.secret_key_encrypted = self._encryptor.encrypt(command.secret_key)
            if command.is_active is not None:
                destination.is_active = command.is_active
            if command.is_default is not None and command.is_default:
                for existing in await self._uow.backup_destinations.list_by_tenant(command.tenant_id):
                    existing.is_default = existing.id == destination.id
                    await self._uow.backup_destinations.save(existing)

            destination.touch()
            await self._uow.backup_destinations.save(destination)
            await self._uow.commit()

        return destination


class DeleteBackupDestinationHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: DeleteBackupDestinationCommand) -> None:
        async with self._uow:
            destination = await self._uow.backup_destinations.get_by_id_and_tenant(
                command.destination_id, command.tenant_id
            )
            if not destination:
                raise NotFoundError("Destination not found")
            await self._uow.backup_destinations.delete(destination.id)
            await self._uow.commit()


class TestBackupDestinationHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._settings = settings or get_settings()

    async def handle(self, tenant_id, destination_id) -> bool:
        async with self._uow:
            destination = await self._uow.backup_destinations.get_by_id_and_tenant(destination_id, tenant_id)
            if not destination:
                raise NotFoundError("Destination not found")
        storage = StorageAdapterFactory.create(destination, self._settings)
        return await storage.test_connection()


class CreateBackupScheduleHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: CreateBackupScheduleCommand) -> BackupSchedule:
        domain = BackupDomainService(self._uow.backup_destinations)
        source_type = domain.validate_source_type(command.source_type)
        cron = domain.validate_cron(command.cron_expression)
        max_versions = domain.validate_max_versions(command.max_versions)
        retention_days = domain.validate_retention_days(command.retention_days)

        async with self._uow:
            destination = await self._uow.backup_destinations.get_by_id_and_tenant(
                command.destination_id, command.tenant_id
            )
            if not destination:
                raise NotFoundError("Destination not found")

            schedule = BackupSchedule(
                tenant_id=command.tenant_id,
                name=domain.validate_name(command.name),
                source_type=source_type,
                resource_id=command.resource_id,
                destination_id=command.destination_id,
                cron_expression=cron,
                max_versions=max_versions,
                retention_days=retention_days,
                next_run_at=compute_next_run(cron, utc_now()),
            )
            await self._uow.backup_schedules.add(schedule)
            await self._uow.commit()

        return schedule


class UpdateBackupScheduleHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: UpdateBackupScheduleCommand) -> BackupSchedule:
        domain = BackupDomainService(self._uow.backup_destinations)

        async with self._uow:
            schedule = await self._uow.backup_schedules.get_by_id_and_tenant(
                command.schedule_id, command.tenant_id
            )
            if not schedule:
                raise NotFoundError("Schedule not found")

            if command.name is not None:
                schedule.name = domain.validate_name(command.name)
            if command.source_type is not None:
                schedule.source_type = domain.validate_source_type(command.source_type)
            if command.resource_id is not None:
                schedule.resource_id = command.resource_id
            if command.destination_id is not None:
                schedule.destination_id = command.destination_id
            if command.cron_expression is not None:
                schedule.cron_expression = domain.validate_cron(command.cron_expression)
                schedule.next_run_at = compute_next_run(schedule.cron_expression, utc_now())
            if command.max_versions is not None:
                schedule.max_versions = domain.validate_max_versions(command.max_versions)
            if command.retention_days is not None:
                schedule.retention_days = domain.validate_retention_days(command.retention_days)

            schedule.touch()
            await self._uow.backup_schedules.save(schedule)
            await self._uow.commit()

        return schedule


class DeleteBackupScheduleHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: DeleteBackupScheduleCommand) -> None:
        async with self._uow:
            schedule = await self._uow.backup_schedules.get_by_id_and_tenant(
                command.schedule_id, command.tenant_id
            )
            if not schedule:
                raise NotFoundError("Schedule not found")
            await self._uow.backup_schedules.delete(schedule.id)
            await self._uow.commit()


class PauseBackupScheduleHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: PauseBackupScheduleCommand) -> BackupSchedule:
        async with self._uow:
            schedule = await self._uow.backup_schedules.get_by_id_and_tenant(
                command.schedule_id, command.tenant_id
            )
            if not schedule:
                raise NotFoundError("Schedule not found")
            schedule.pause()
            await self._uow.backup_schedules.save(schedule)
            await self._uow.commit()
        return schedule


class ResumeBackupScheduleHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: ResumeBackupScheduleCommand) -> BackupSchedule:
        async with self._uow:
            schedule = await self._uow.backup_schedules.get_by_id_and_tenant(
                command.schedule_id, command.tenant_id
            )
            if not schedule:
                raise NotFoundError("Schedule not found")
            schedule.resume(compute_next_run(schedule.cron_expression, utc_now()))
            await self._uow.backup_schedules.save(schedule)
            await self._uow.commit()
        return schedule


class RunBackupScheduleHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._settings = settings or get_settings()

    async def handle(self, command: RunBackupScheduleCommand):
        async with self._uow:
            schedule = await self._uow.backup_schedules.get_by_id_and_tenant(
                command.schedule_id, command.tenant_id
            )
            if not schedule:
                raise NotFoundError("Schedule not found")
            destination = await self._uow.backup_destinations.get_by_id(schedule.destination_id)
            if not destination:
                raise NotFoundError("Destination not found")

            engine = BackupEngine(self._uow, self._settings)
            job = await engine.run_backup(
                tenant_id=schedule.tenant_id,
                destination=destination,
                source_type=schedule.source_type,
                resource_id=schedule.resource_id,
                name=f"{schedule.name}-manual",
                trigger_type=BackupTriggerType.MANUAL,
                schedule=schedule,
            )
            await self._uow.commit()
        return job


class CreateBackupJobHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._settings = settings or get_settings()

    async def handle(self, command: CreateBackupJobCommand):
        domain = BackupDomainService(self._uow.backup_destinations)
        source_type = domain.validate_source_type(command.source_type)

        async with self._uow:
            destination = await self._uow.backup_destinations.get_by_id_and_tenant(
                command.destination_id, command.tenant_id
            )
            if not destination:
                raise NotFoundError("Destination not found")

            engine = BackupEngine(self._uow, self._settings)
            job = await engine.run_backup(
                tenant_id=command.tenant_id,
                destination=destination,
                source_type=source_type,
                resource_id=command.resource_id,
                name=command.name or f"backup-{utc_now().strftime('%Y%m%d%H%M')}",
                trigger_type=BackupTriggerType.MANUAL,
                max_versions=domain.validate_max_versions(command.max_versions),
                retention_days=domain.validate_retention_days(command.retention_days),
            )
            await self._uow.commit()
        return job


class RestoreBackupJobHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._settings = settings or get_settings()

    async def handle(self, command: RestoreBackupJobCommand):
        async with self._uow:
            job = await self._uow.backup_jobs.get_by_id_and_tenant(command.job_id, command.tenant_id)
            if not job:
                raise NotFoundError("Backup job not found")
            destination = await self._uow.backup_destinations.get_by_id(job.destination_id)
            if not destination:
                raise NotFoundError("Destination not found")

            engine = BackupEngine(self._uow, self._settings)
            job = await engine.restore_backup(job, destination)
            await self._uow.commit()
        return job


class DeleteBackupJobHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._settings = settings or get_settings()

    async def handle(self, command: DeleteBackupJobCommand) -> None:
        async with self._uow:
            job = await self._uow.backup_jobs.get_by_id_and_tenant(command.job_id, command.tenant_id)
            if not job:
                raise NotFoundError("Backup job not found")
            destination = await self._uow.backup_destinations.get_by_id(job.destination_id)
            if destination:
                engine = BackupEngine(self._uow, self._settings)
                await engine.delete_backup_file(job, destination)
            await self._uow.backup_jobs.delete(job.id)
            await self._uow.commit()
