import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from controlbox.config.settings import Settings
from controlbox.modules.backups.domain.entities import (
    BackupDestination,
    BackupJob,
    BackupJobStatus,
    BackupSchedule,
    BackupSourceType,
    BackupTriggerType,
)
from controlbox.modules.backups.domain.services import BackupDomainService
from controlbox.modules.backups.infrastructure.executors import BackupExecutorFactory
from controlbox.modules.backups.infrastructure.storage import (
    StorageAdapterFactory,
    compute_file_checksum,
)
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import NotFoundError, utc_now


class BackupEngine:
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._settings = settings
        self._domain = BackupDomainService(uow.backup_destinations)

    async def run_backup(
        self,
        tenant_id: UUID,
        destination: BackupDestination,
        source_type: BackupSourceType,
        resource_id: UUID | None,
        name: str,
        trigger_type: BackupTriggerType,
        schedule: BackupSchedule | None = None,
        max_versions: int = 10,
        retention_days: int = 30,
    ) -> BackupJob:
        resource_key = self._domain.build_resource_key(source_type, resource_id)
        latest = await self._uow.backup_jobs.get_latest_version(tenant_id, resource_key)
        version_number = latest + 1

        job = BackupJob(
            tenant_id=tenant_id,
            schedule_id=schedule.id if schedule else None,
            destination_id=destination.id,
            name=name,
            source_type=source_type,
            resource_id=resource_id,
            resource_key=resource_key,
            trigger_type=trigger_type,
            status=BackupJobStatus.PENDING,
            version_number=version_number,
            retention_days=retention_days,
        )

        await self._uow.backup_jobs.add(job)
        job.mark_running()
        await self._uow.backup_jobs.save(job)

        work_dir = Path(tempfile.mkdtemp(prefix="cb-backup-"))
        local_archive: Path | None = None

        try:
            executor = BackupExecutorFactory(self._uow, self._settings).get(source_type)
            local_archive, resource_name, metadata = await executor.backup(tenant_id, resource_id, work_dir)
            job.resource_name = resource_name
            job.metadata = metadata

            storage = StorageAdapterFactory.create(destination, self._settings)
            remote_key = self._build_storage_key(tenant_id, source_type, resource_id, job.id, version_number, local_archive.suffix)
            stored_path = await storage.upload(local_archive, remote_key)
            checksum = compute_file_checksum(local_archive)
            size_bytes = local_archive.stat().st_size

            job.mark_completed(stored_path, size_bytes, checksum)
            await self._uow.backup_jobs.save(job)

            await self._prune_versions(
                tenant_id,
                resource_key,
                schedule.max_versions if schedule else max_versions,
                destination,
            )
            await self._prune_by_retention(
                tenant_id,
                resource_key,
                retention_days,
                destination,
            )
        except Exception as exc:
            job.mark_failed(str(exc))
            await self._uow.backup_jobs.save(job)
            raise
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

        return job

    async def restore_backup(self, job: BackupJob, destination: BackupDestination) -> BackupJob:
        if job.status != BackupJobStatus.COMPLETED:
            raise ValueError("Only completed backups can be restored")

        job.mark_restoring()
        await self._uow.backup_jobs.save(job)

        work_dir = Path(tempfile.mkdtemp(prefix="cb-restore-"))
        local_path = work_dir / "restore-archive"

        try:
            storage = StorageAdapterFactory.create(destination, self._settings)
            await storage.download(job.storage_path, local_path)

            executor = BackupExecutorFactory(self._uow, self._settings).get(job.source_type)
            await executor.restore(job.tenant_id, job.resource_id, local_path)

            job.status = BackupJobStatus.COMPLETED
            job.touch()
            await self._uow.backup_jobs.save(job)
        except Exception as exc:
            job.mark_failed(str(exc))
            await self._uow.backup_jobs.save(job)
            raise
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

        return job

    async def delete_backup_file(self, job: BackupJob, destination: BackupDestination) -> None:
        if not job.storage_path:
            return
        storage = StorageAdapterFactory.create(destination, self._settings)
        try:
            await storage.delete(job.storage_path)
        except Exception:
            pass

    async def _prune_versions(
        self,
        tenant_id: UUID,
        resource_key: str,
        max_versions: int,
        destination: BackupDestination,
    ) -> None:
        versions = await self._uow.backup_jobs.list_versions(tenant_id, resource_key)
        if len(versions) <= max_versions:
            return

        to_delete = versions[max_versions:]
        for old_job in to_delete:
            await self.delete_backup_file(old_job, destination)
            await self._uow.backup_jobs.delete(old_job.id)

    async def _prune_by_retention(
        self,
        tenant_id: UUID,
        resource_key: str,
        retention_days: int,
        destination: BackupDestination,
    ) -> None:
        if retention_days <= 0:
            return
        from datetime import timedelta

        cutoff = utc_now() - timedelta(days=retention_days)
        versions = await self._uow.backup_jobs.list_versions(tenant_id, resource_key)
        for job in versions:
            if job.created_at < cutoff:
                await self.delete_backup_file(job, destination)
                await self._uow.backup_jobs.delete(job.id)

    def _build_storage_key(
        self,
        tenant_id: UUID,
        source_type: BackupSourceType,
        resource_id: UUID | None,
        job_id: UUID,
        version: int,
        suffix: str,
    ) -> str:
        resource_part = str(resource_id) if resource_id else "all"
        ext = suffix if suffix.startswith(".") else f".{suffix}" if suffix else ".tar.gz"
        return f"{tenant_id}/{source_type.value}/{resource_part}/v{version:04d}-{job_id}{ext}"


def compute_next_run(cron_expression: str, base: datetime | None = None) -> datetime:
    from croniter import croniter

    start = base or utc_now()
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    iterator = croniter(cron_expression, start)
    next_dt = iterator.get_next(datetime)
    if next_dt.tzinfo is None:
        next_dt = next_dt.replace(tzinfo=timezone.utc)
    return next_dt
