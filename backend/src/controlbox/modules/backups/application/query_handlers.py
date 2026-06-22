from controlbox.config.settings import get_settings
from controlbox.modules.backups.application.queries import (
    BackupDestinationResponse,
    BackupJobResponse,
    BackupScheduleResponse,
    BackupStatsResponse,
    GetBackupDestinationQuery,
    GetBackupJobQuery,
    GetBackupScheduleQuery,
    GetBackupStatsQuery,
    ListBackupDestinationsQuery,
    ListBackupJobsQuery,
    ListBackupSchedulesQuery,
    ListBackupVersionsQuery,
)
from controlbox.modules.backups.domain.entities import BackupJobStatus
from controlbox.modules.backups.infrastructure.storage import StorageAdapterFactory
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import NotFoundError


def to_destination_response(dest) -> BackupDestinationResponse:
    return BackupDestinationResponse(
        id=dest.id,
        tenant_id=dest.tenant_id,
        name=dest.name,
        destination_type=dest.destination_type.value,
        bucket=dest.bucket,
        endpoint=dest.endpoint,
        region=dest.region,
        prefix=dest.prefix,
        local_path=dest.local_path,
        is_default=dest.is_default,
        is_active=dest.is_active,
        created_at=dest.created_at,
        updated_at=dest.updated_at,
    )


def to_schedule_response(schedule) -> BackupScheduleResponse:
    return BackupScheduleResponse(
        id=schedule.id,
        tenant_id=schedule.tenant_id,
        name=schedule.name,
        source_type=schedule.source_type.value,
        resource_id=schedule.resource_id,
        destination_id=schedule.destination_id,
        cron_expression=schedule.cron_expression,
        max_versions=schedule.max_versions,
        retention_days=schedule.retention_days,
        is_active=schedule.is_active,
        last_run_at=schedule.last_run_at,
        next_run_at=schedule.next_run_at,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
    )


def to_job_response(job) -> BackupJobResponse:
    return BackupJobResponse(
        id=job.id,
        tenant_id=job.tenant_id,
        schedule_id=job.schedule_id,
        destination_id=job.destination_id,
        name=job.name,
        source_type=job.source_type.value,
        resource_id=job.resource_id,
        resource_name=job.resource_name,
        resource_key=job.resource_key,
        trigger_type=job.trigger_type.value,
        status=job.status.value,
        version_number=job.version_number,
        storage_path=job.storage_path,
        size_bytes=job.size_bytes,
        checksum=job.checksum,
        metadata=job.metadata,
        retention_days=job.retention_days,
        error_message=job.error_message,
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


class ListBackupDestinationsHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListBackupDestinationsQuery) -> list[BackupDestinationResponse]:
        async with self._uow:
            items = await self._uow.backup_destinations.list_by_tenant(query.tenant_id)
        return [to_destination_response(i) for i in items]


class GetBackupDestinationHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: GetBackupDestinationQuery) -> BackupDestinationResponse:
        async with self._uow:
            item = await self._uow.backup_destinations.get_by_id_and_tenant(
                query.destination_id, query.tenant_id
            )
            if not item:
                raise NotFoundError("Destination not found")
        return to_destination_response(item)


class ListBackupSchedulesHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListBackupSchedulesQuery) -> list[BackupScheduleResponse]:
        async with self._uow:
            items = await self._uow.backup_schedules.list_by_tenant(query.tenant_id)
        return [to_schedule_response(i) for i in items]


class GetBackupScheduleHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: GetBackupScheduleQuery) -> BackupScheduleResponse:
        async with self._uow:
            item = await self._uow.backup_schedules.get_by_id_and_tenant(
                query.schedule_id, query.tenant_id
            )
            if not item:
                raise NotFoundError("Schedule not found")
        return to_schedule_response(item)


class ListBackupJobsHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListBackupJobsQuery) -> list[BackupJobResponse]:
        async with self._uow:
            items = await self._uow.backup_jobs.list_by_tenant(query.tenant_id, query.source_type)
        return [to_job_response(i) for i in items]


class GetBackupJobHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: GetBackupJobQuery) -> BackupJobResponse:
        async with self._uow:
            item = await self._uow.backup_jobs.get_by_id_and_tenant(query.job_id, query.tenant_id)
            if not item:
                raise NotFoundError("Backup job not found")
        return to_job_response(item)


class ListBackupVersionsHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListBackupVersionsQuery) -> list[BackupJobResponse]:
        async with self._uow:
            job = await self._uow.backup_jobs.get_by_id_and_tenant(query.job_id, query.tenant_id)
            if not job:
                raise NotFoundError("Backup job not found")
            versions = await self._uow.backup_jobs.list_versions(query.tenant_id, job.resource_key)
        return [to_job_response(v) for v in versions]


class GetBackupStatsHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: GetBackupStatsQuery) -> BackupStatsResponse:
        async with self._uow:
            jobs = await self._uow.backup_jobs.list_by_tenant(query.tenant_id)
            schedules = await self._uow.backup_schedules.list_by_tenant(query.tenant_id)

        completed = [j for j in jobs if j.status == BackupJobStatus.COMPLETED]
        failed = [j for j in jobs if j.status == BackupJobStatus.FAILED]
        active_schedules = [s for s in schedules if s.is_active]
        next_run = min(
            (s.next_run_at for s in active_schedules if s.next_run_at),
            default=None,
        )

        return BackupStatsResponse(
            total_jobs=len(jobs),
            completed_jobs=len(completed),
            failed_jobs=len(failed),
            total_size_bytes=sum(j.size_bytes for j in completed),
            active_schedules=len(active_schedules),
            next_scheduled_at=next_run,
        )


class GetBackupDownloadUrlHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow
        self._settings = get_settings()

    async def handle(self, tenant_id, job_id) -> str | None:
        async with self._uow:
            job = await self._uow.backup_jobs.get_by_id_and_tenant(job_id, tenant_id)
            if not job:
                raise NotFoundError("Backup job not found")
            destination = await self._uow.backup_destinations.get_by_id(job.destination_id)
            if not destination:
                raise NotFoundError("Destination not found")

        storage = StorageAdapterFactory.create(destination, self._settings)
        return await storage.get_download_url(job.storage_path)
