from controlbox.modules.backups.domain.entities import (
    BackupDestination,
    BackupDestinationType,
    BackupJob,
    BackupJobStatus,
    BackupSchedule,
    BackupSourceType,
    BackupTriggerType,
)
from controlbox.modules.backups.infrastructure.models import (
    BackupDestinationModel,
    BackupJobModel,
    BackupScheduleModel,
)


def to_backup_destination(model: BackupDestinationModel) -> BackupDestination:
    return BackupDestination(
        id=model.id,
        tenant_id=model.tenant_id,
        name=model.name,
        destination_type=BackupDestinationType(model.destination_type),
        bucket=model.bucket,
        endpoint=model.endpoint,
        region=model.region,
        prefix=model.prefix,
        local_path=model.local_path,
        access_key_encrypted=model.access_key_encrypted,
        secret_key_encrypted=model.secret_key_encrypted,
        is_default=model.is_default,
        is_active=model.is_active,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def to_backup_schedule(model: BackupScheduleModel) -> BackupSchedule:
    return BackupSchedule(
        id=model.id,
        tenant_id=model.tenant_id,
        name=model.name,
        source_type=BackupSourceType(model.source_type),
        resource_id=model.resource_id,
        destination_id=model.destination_id,
        cron_expression=model.cron_expression,
        max_versions=model.max_versions,
        retention_days=model.retention_days,
        is_active=model.is_active,
        last_run_at=model.last_run_at,
        next_run_at=model.next_run_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def to_backup_job(model: BackupJobModel) -> BackupJob:
    return BackupJob(
        id=model.id,
        tenant_id=model.tenant_id,
        schedule_id=model.schedule_id,
        destination_id=model.destination_id,
        name=model.name,
        source_type=BackupSourceType(model.source_type),
        resource_id=model.resource_id,
        resource_name=model.resource_name,
        resource_key=model.resource_key,
        trigger_type=BackupTriggerType(model.trigger_type),
        status=BackupJobStatus(model.status),
        version_number=model.version_number,
        storage_path=model.storage_path,
        size_bytes=model.size_bytes,
        checksum=model.checksum,
        metadata=model.metadata_,
        retention_days=model.retention_days,
        error_message=model.error_message,
        started_at=model.started_at,
        completed_at=model.completed_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
