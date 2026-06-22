from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from controlbox.modules.backups.api.schemas import (
    BackupDestinationSchema,
    BackupDownloadSchema,
    BackupJobSchema,
    BackupScheduleSchema,
    BackupStatsSchema,
    BackupTestResultSchema,
    CreateBackupDestinationRequest,
    CreateBackupJobRequest,
    CreateBackupScheduleRequest,
    UpdateBackupDestinationRequest,
    UpdateBackupScheduleRequest,
)
from controlbox.modules.backups.application.command_handlers import (
    CreateBackupDestinationHandler,
    CreateBackupJobHandler,
    CreateBackupScheduleHandler,
    DeleteBackupDestinationHandler,
    DeleteBackupJobHandler,
    DeleteBackupScheduleHandler,
    PauseBackupScheduleHandler,
    RestoreBackupJobHandler,
    ResumeBackupScheduleHandler,
    RunBackupScheduleHandler,
    TestBackupDestinationHandler,
    UpdateBackupDestinationHandler,
    UpdateBackupScheduleHandler,
)
from controlbox.modules.backups.application.commands import (
    CreateBackupDestinationCommand,
    CreateBackupJobCommand,
    CreateBackupScheduleCommand,
    DeleteBackupDestinationCommand,
    DeleteBackupJobCommand,
    DeleteBackupScheduleCommand,
    PauseBackupScheduleCommand,
    RestoreBackupJobCommand,
    ResumeBackupScheduleCommand,
    RunBackupScheduleCommand,
    UpdateBackupDestinationCommand,
    UpdateBackupScheduleCommand,
)
from controlbox.modules.backups.application.queries import (
    GetBackupDestinationQuery,
    GetBackupJobQuery,
    GetBackupScheduleQuery,
    GetBackupStatsQuery,
    ListBackupDestinationsQuery,
    ListBackupJobsQuery,
    ListBackupSchedulesQuery,
    ListBackupVersionsQuery,
)
from controlbox.modules.backups.application.query_handlers import (
    GetBackupDestinationHandler,
    GetBackupDownloadUrlHandler,
    GetBackupJobHandler,
    GetBackupScheduleHandler,
    GetBackupStatsHandler,
    ListBackupDestinationsHandler,
    ListBackupJobsHandler,
    ListBackupSchedulesHandler,
    ListBackupVersionsHandler,
    to_destination_response,
    to_job_response,
    to_schedule_response,
)
from controlbox.modules.identity.api.dependencies import (
    RequestContext,
    get_current_context,
    get_unit_of_work,
    map_domain_exception,
    require_permission,
)
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import ForbiddenError


router = APIRouter(prefix="/backups", tags=["backups"])


def _require_tenant(context: RequestContext) -> UUID:
    if not context.tenant_id:
        raise map_domain_exception(ForbiddenError("Tenant context required"))
    return context.tenant_id


def _to_dest_schema(r) -> BackupDestinationSchema:
    return BackupDestinationSchema(**r.__dict__)


def _to_sched_schema(r) -> BackupScheduleSchema:
    return BackupScheduleSchema(**r.__dict__)


def _to_job_schema(r) -> BackupJobSchema:
    return BackupJobSchema(**r.__dict__)


@router.get("/stats", response_model=BackupStatsSchema)
async def get_backup_stats(
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("backups.read"))],
) -> BackupStatsSchema:
    tenant_id = _require_tenant(context)
    stats = await GetBackupStatsHandler(uow).handle(GetBackupStatsQuery(tenant_id=tenant_id))
    return BackupStatsSchema(**stats.__dict__)


@router.get("/destinations", response_model=list[BackupDestinationSchema])
async def list_destinations(
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("backups.read"))],
) -> list[BackupDestinationSchema]:
    tenant_id = _require_tenant(context)
    items = await ListBackupDestinationsHandler(uow).handle(ListBackupDestinationsQuery(tenant_id=tenant_id))
    return [_to_dest_schema(i) for i in items]


@router.post("/destinations", response_model=BackupDestinationSchema, status_code=201)
async def create_destination(
    body: CreateBackupDestinationRequest,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("backups.manage"))],
) -> BackupDestinationSchema:
    tenant_id = _require_tenant(context)
    dest = await CreateBackupDestinationHandler(uow).handle(
        CreateBackupDestinationCommand(tenant_id=tenant_id, **body.model_dump())
    )
    return _to_dest_schema(to_destination_response(dest))


@router.get("/destinations/{destination_id}", response_model=BackupDestinationSchema)
async def get_destination(
    destination_id: UUID,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("backups.read"))],
) -> BackupDestinationSchema:
    tenant_id = _require_tenant(context)
    item = await GetBackupDestinationHandler(uow).handle(
        GetBackupDestinationQuery(tenant_id=tenant_id, destination_id=destination_id)
    )
    return _to_dest_schema(item)


@router.patch("/destinations/{destination_id}", response_model=BackupDestinationSchema)
async def update_destination(
    destination_id: UUID,
    body: UpdateBackupDestinationRequest,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("backups.manage"))],
) -> BackupDestinationSchema:
    tenant_id = _require_tenant(context)
    dest = await UpdateBackupDestinationHandler(uow).handle(
        UpdateBackupDestinationCommand(
            tenant_id=tenant_id,
            destination_id=destination_id,
            **body.model_dump(exclude_unset=True),
        )
    )
    return _to_dest_schema(to_destination_response(dest))


@router.delete("/destinations/{destination_id}", status_code=204)
async def delete_destination(
    destination_id: UUID,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("backups.manage"))],
) -> None:
    tenant_id = _require_tenant(context)
    await DeleteBackupDestinationHandler(uow).handle(
        DeleteBackupDestinationCommand(tenant_id=tenant_id, destination_id=destination_id)
    )


@router.post("/destinations/{destination_id}/test", response_model=BackupTestResultSchema)
async def test_destination(
    destination_id: UUID,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("backups.manage"))],
) -> BackupTestResultSchema:
    tenant_id = _require_tenant(context)
    success = await TestBackupDestinationHandler(uow).handle(tenant_id, destination_id)
    return BackupTestResultSchema(success=success)


@router.get("/schedules", response_model=list[BackupScheduleSchema])
async def list_schedules(
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("backups.read"))],
) -> list[BackupScheduleSchema]:
    tenant_id = _require_tenant(context)
    items = await ListBackupSchedulesHandler(uow).handle(ListBackupSchedulesQuery(tenant_id=tenant_id))
    return [_to_sched_schema(i) for i in items]


@router.post("/schedules", response_model=BackupScheduleSchema, status_code=201)
async def create_schedule(
    body: CreateBackupScheduleRequest,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("backups.manage"))],
) -> BackupScheduleSchema:
    tenant_id = _require_tenant(context)
    schedule = await CreateBackupScheduleHandler(uow).handle(
        CreateBackupScheduleCommand(tenant_id=tenant_id, **body.model_dump())
    )
    return _to_sched_schema(to_schedule_response(schedule))


@router.get("/schedules/{schedule_id}", response_model=BackupScheduleSchema)
async def get_schedule(
    schedule_id: UUID,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("backups.read"))],
) -> BackupScheduleSchema:
    tenant_id = _require_tenant(context)
    item = await GetBackupScheduleHandler(uow).handle(
        GetBackupScheduleQuery(tenant_id=tenant_id, schedule_id=schedule_id)
    )
    return _to_sched_schema(item)


@router.patch("/schedules/{schedule_id}", response_model=BackupScheduleSchema)
async def update_schedule(
    schedule_id: UUID,
    body: UpdateBackupScheduleRequest,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("backups.manage"))],
) -> BackupScheduleSchema:
    tenant_id = _require_tenant(context)
    schedule = await UpdateBackupScheduleHandler(uow).handle(
        UpdateBackupScheduleCommand(
            tenant_id=tenant_id,
            schedule_id=schedule_id,
            **body.model_dump(exclude_unset=True),
        )
    )
    return _to_sched_schema(to_schedule_response(schedule))


@router.delete("/schedules/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id: UUID,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("backups.manage"))],
) -> None:
    tenant_id = _require_tenant(context)
    await DeleteBackupScheduleHandler(uow).handle(
        DeleteBackupScheduleCommand(tenant_id=tenant_id, schedule_id=schedule_id)
    )


@router.put("/schedules/{schedule_id}/pause", response_model=BackupScheduleSchema)
async def pause_schedule(
    schedule_id: UUID,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("backups.manage"))],
) -> BackupScheduleSchema:
    tenant_id = _require_tenant(context)
    schedule = await PauseBackupScheduleHandler(uow).handle(
        PauseBackupScheduleCommand(tenant_id=tenant_id, schedule_id=schedule_id)
    )
    return _to_sched_schema(to_schedule_response(schedule))


@router.put("/schedules/{schedule_id}/resume", response_model=BackupScheduleSchema)
async def resume_schedule(
    schedule_id: UUID,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("backups.manage"))],
) -> BackupScheduleSchema:
    tenant_id = _require_tenant(context)
    schedule = await ResumeBackupScheduleHandler(uow).handle(
        ResumeBackupScheduleCommand(tenant_id=tenant_id, schedule_id=schedule_id)
    )
    return _to_sched_schema(to_schedule_response(schedule))


@router.post("/schedules/{schedule_id}/run", response_model=BackupJobSchema, status_code=201)
async def run_schedule(
    schedule_id: UUID,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("backups.manage"))],
) -> BackupJobSchema:
    tenant_id = _require_tenant(context)
    job = await RunBackupScheduleHandler(uow).handle(
        RunBackupScheduleCommand(tenant_id=tenant_id, schedule_id=schedule_id)
    )
    return _to_job_schema(to_job_response(job))


@router.get("/jobs", response_model=list[BackupJobSchema])
async def list_jobs(
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("backups.read"))],
    source_type: str | None = Query(default=None),
) -> list[BackupJobSchema]:
    tenant_id = _require_tenant(context)
    items = await ListBackupJobsHandler(uow).handle(
        ListBackupJobsQuery(tenant_id=tenant_id, source_type=source_type)
    )
    return [_to_job_schema(i) for i in items]


@router.post("/jobs", response_model=BackupJobSchema, status_code=201)
async def create_job(
    body: CreateBackupJobRequest,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("backups.manage"))],
) -> BackupJobSchema:
    tenant_id = _require_tenant(context)
    job = await CreateBackupJobHandler(uow).handle(
        CreateBackupJobCommand(tenant_id=tenant_id, **body.model_dump())
    )
    return _to_job_schema(to_job_response(job))


@router.get("/jobs/{job_id}", response_model=BackupJobSchema)
async def get_job(
    job_id: UUID,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("backups.read"))],
) -> BackupJobSchema:
    tenant_id = _require_tenant(context)
    item = await GetBackupJobHandler(uow).handle(GetBackupJobQuery(tenant_id=tenant_id, job_id=job_id))
    return _to_job_schema(item)


@router.delete("/jobs/{job_id}", status_code=204)
async def delete_job(
    job_id: UUID,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("backups.manage"))],
) -> None:
    tenant_id = _require_tenant(context)
    await DeleteBackupJobHandler(uow).handle(
        DeleteBackupJobCommand(tenant_id=tenant_id, job_id=job_id)
    )


@router.post("/jobs/{job_id}/restore", response_model=BackupJobSchema)
async def restore_job(
    job_id: UUID,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("backups.manage"))],
) -> BackupJobSchema:
    tenant_id = _require_tenant(context)
    job = await RestoreBackupJobHandler(uow).handle(
        RestoreBackupJobCommand(tenant_id=tenant_id, job_id=job_id)
    )
    return _to_job_schema(to_job_response(job))


@router.get("/jobs/{job_id}/versions", response_model=list[BackupJobSchema])
async def list_versions(
    job_id: UUID,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("backups.read"))],
) -> list[BackupJobSchema]:
    tenant_id = _require_tenant(context)
    versions = await ListBackupVersionsHandler(uow).handle(
        ListBackupVersionsQuery(tenant_id=tenant_id, job_id=job_id)
    )
    return [_to_job_schema(v) for v in versions]


@router.get("/jobs/{job_id}/download", response_model=BackupDownloadSchema)
async def download_job(
    job_id: UUID,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("backups.read"))],
) -> BackupDownloadSchema:
    tenant_id = _require_tenant(context)
    job = await GetBackupJobHandler(uow).handle(GetBackupJobQuery(tenant_id=tenant_id, job_id=job_id))
    url = await GetBackupDownloadUrlHandler(uow).handle(tenant_id, job_id)
    return BackupDownloadSchema(download_url=url, storage_path=job.storage_path)
