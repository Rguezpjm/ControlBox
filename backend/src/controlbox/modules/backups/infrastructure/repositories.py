from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from controlbox.modules.backups.domain.entities import BackupDestination, BackupJob, BackupSchedule
from controlbox.modules.backups.domain.repositories import (
    BackupDestinationRepository,
    BackupJobRepository,
    BackupScheduleRepository,
)
from controlbox.modules.backups.infrastructure.mappers import (
    to_backup_destination,
    to_backup_job,
    to_backup_schedule,
)
from controlbox.modules.backups.infrastructure.models import (
    BackupDestinationModel,
    BackupJobModel,
    BackupScheduleModel,
)


class SqlAlchemyBackupDestinationRepository(BackupDestinationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, destination: BackupDestination) -> None:
        self._session.add(
            BackupDestinationModel(
                id=destination.id,
                tenant_id=destination.tenant_id,
                name=destination.name,
                destination_type=destination.destination_type.value,
                bucket=destination.bucket,
                endpoint=destination.endpoint,
                region=destination.region,
                prefix=destination.prefix,
                local_path=destination.local_path,
                access_key_encrypted=destination.access_key_encrypted,
                secret_key_encrypted=destination.secret_key_encrypted,
                is_default=destination.is_default,
                is_active=destination.is_active,
            )
        )

    async def save(self, destination: BackupDestination) -> None:
        result = await self._session.execute(
            select(BackupDestinationModel).where(BackupDestinationModel.id == destination.id)
        )
        model = result.scalar_one()
        model.name = destination.name
        model.bucket = destination.bucket
        model.endpoint = destination.endpoint
        model.region = destination.region
        model.prefix = destination.prefix
        model.local_path = destination.local_path
        model.access_key_encrypted = destination.access_key_encrypted
        model.secret_key_encrypted = destination.secret_key_encrypted
        model.is_default = destination.is_default
        model.is_active = destination.is_active

    async def get_by_id(self, destination_id: UUID) -> BackupDestination | None:
        result = await self._session.execute(
            select(BackupDestinationModel).where(BackupDestinationModel.id == destination_id)
        )
        model = result.scalar_one_or_none()
        return to_backup_destination(model) if model else None

    async def get_by_id_and_tenant(self, destination_id: UUID, tenant_id: UUID) -> BackupDestination | None:
        result = await self._session.execute(
            select(BackupDestinationModel).where(
                BackupDestinationModel.id == destination_id,
                BackupDestinationModel.tenant_id == tenant_id,
            )
        )
        model = result.scalar_one_or_none()
        return to_backup_destination(model) if model else None

    async def list_by_tenant(self, tenant_id: UUID) -> list[BackupDestination]:
        result = await self._session.execute(
            select(BackupDestinationModel)
            .where(BackupDestinationModel.tenant_id == tenant_id)
            .order_by(BackupDestinationModel.created_at.desc())
        )
        return [to_backup_destination(m) for m in result.scalars().all()]

    async def delete(self, destination_id: UUID) -> None:
        await self._session.execute(
            delete(BackupDestinationModel).where(BackupDestinationModel.id == destination_id)
        )


class SqlAlchemyBackupScheduleRepository(BackupScheduleRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, schedule: BackupSchedule) -> None:
        self._session.add(
            BackupScheduleModel(
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
            )
        )

    async def save(self, schedule: BackupSchedule) -> None:
        result = await self._session.execute(
            select(BackupScheduleModel).where(BackupScheduleModel.id == schedule.id)
        )
        model = result.scalar_one()
        model.name = schedule.name
        model.source_type = schedule.source_type.value
        model.resource_id = schedule.resource_id
        model.destination_id = schedule.destination_id
        model.cron_expression = schedule.cron_expression
        model.max_versions = schedule.max_versions
        model.retention_days = schedule.retention_days
        model.is_active = schedule.is_active
        model.last_run_at = schedule.last_run_at
        model.next_run_at = schedule.next_run_at

    async def get_by_id(self, schedule_id: UUID) -> BackupSchedule | None:
        result = await self._session.execute(
            select(BackupScheduleModel).where(BackupScheduleModel.id == schedule_id)
        )
        model = result.scalar_one_or_none()
        return to_backup_schedule(model) if model else None

    async def get_by_id_and_tenant(self, schedule_id: UUID, tenant_id: UUID) -> BackupSchedule | None:
        result = await self._session.execute(
            select(BackupScheduleModel).where(
                BackupScheduleModel.id == schedule_id,
                BackupScheduleModel.tenant_id == tenant_id,
            )
        )
        model = result.scalar_one_or_none()
        return to_backup_schedule(model) if model else None

    async def list_by_tenant(self, tenant_id: UUID) -> list[BackupSchedule]:
        result = await self._session.execute(
            select(BackupScheduleModel)
            .where(BackupScheduleModel.tenant_id == tenant_id)
            .order_by(BackupScheduleModel.created_at.desc())
        )
        return [to_backup_schedule(m) for m in result.scalars().all()]

    async def list_due(self, before: datetime) -> list[BackupSchedule]:
        result = await self._session.execute(
            select(BackupScheduleModel).where(
                BackupScheduleModel.is_active.is_(True),
                BackupScheduleModel.next_run_at.is_not(None),
                BackupScheduleModel.next_run_at <= before,
            )
        )
        return [to_backup_schedule(m) for m in result.scalars().all()]

    async def delete(self, schedule_id: UUID) -> None:
        await self._session.execute(
            delete(BackupScheduleModel).where(BackupScheduleModel.id == schedule_id)
        )


class SqlAlchemyBackupJobRepository(BackupJobRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, job: BackupJob) -> None:
        self._session.add(
            BackupJobModel(
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
                metadata_=job.metadata,
                retention_days=job.retention_days,
                error_message=job.error_message,
                started_at=job.started_at,
                completed_at=job.completed_at,
            )
        )

    async def save(self, job: BackupJob) -> None:
        result = await self._session.execute(
            select(BackupJobModel).where(BackupJobModel.id == job.id)
        )
        model = result.scalar_one()
        model.name = job.name
        model.status = job.status.value
        model.version_number = job.version_number
        model.storage_path = job.storage_path
        model.size_bytes = job.size_bytes
        model.checksum = job.checksum
        model.metadata_ = job.metadata
        model.error_message = job.error_message
        model.started_at = job.started_at
        model.completed_at = job.completed_at

    async def get_by_id(self, job_id: UUID) -> BackupJob | None:
        result = await self._session.execute(
            select(BackupJobModel).where(BackupJobModel.id == job_id)
        )
        model = result.scalar_one_or_none()
        return to_backup_job(model) if model else None

    async def get_by_id_and_tenant(self, job_id: UUID, tenant_id: UUID) -> BackupJob | None:
        result = await self._session.execute(
            select(BackupJobModel).where(
                BackupJobModel.id == job_id,
                BackupJobModel.tenant_id == tenant_id,
            )
        )
        model = result.scalar_one_or_none()
        return to_backup_job(model) if model else None

    async def list_by_tenant(self, tenant_id: UUID, source_type: str | None = None) -> list[BackupJob]:
        query = select(BackupJobModel).where(BackupJobModel.tenant_id == tenant_id)
        if source_type:
            query = query.where(BackupJobModel.source_type == source_type)
        result = await self._session.execute(query.order_by(BackupJobModel.created_at.desc()))
        return [to_backup_job(m) for m in result.scalars().all()]

    async def list_versions(self, tenant_id: UUID, resource_key: str) -> list[BackupJob]:
        result = await self._session.execute(
            select(BackupJobModel)
            .where(
                BackupJobModel.tenant_id == tenant_id,
                BackupJobModel.resource_key == resource_key,
                BackupJobModel.status == "completed",
            )
            .order_by(BackupJobModel.version_number.desc())
        )
        return [to_backup_job(m) for m in result.scalars().all()]

    async def get_latest_version(self, tenant_id: UUID, resource_key: str) -> int:
        result = await self._session.execute(
            select(func.max(BackupJobModel.version_number)).where(
                BackupJobModel.tenant_id == tenant_id,
                BackupJobModel.resource_key == resource_key,
            )
        )
        value = result.scalar_one()
        return int(value or 0)

    async def delete(self, job_id: UUID) -> None:
        await self._session.execute(delete(BackupJobModel).where(BackupJobModel.id == job_id))
