from typing import Annotated
from uuid import UUID

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from controlbox.config.settings import Settings, get_settings
from controlbox.shared.infrastructure.version_info import resolve_controlbox_version
from controlbox.modules.identity.api.dependencies import (
    RequestContext,
    get_current_context,
    get_unit_of_work,
    require_permission,
)
from controlbox.modules.platform.api.schemas import (
    AcknowledgeSecretRequest,
    AlertThresholdsSchema,
    PanelActionResponse,
    PanelConfigSchema,
    PanelSettingsSchema,
    PlatformOverviewSchema,
    ResourceAlertSchema,
    SecretsRotationSchema,
    SecretRotationItemSchema,
    ServerTimeSchema,
    SetupChecklistItemSchema,
    SetupChecklistSchema,
    SystemInfoSchema,
    OperationResultSchema,
    UpdateCheckSchema,
    UpdatePanelConfigRequest,
    UpdatePanelConfigResponse,
    UpdatePanelSettingsRequest,
    UpdateSetupChecklistRequest,
    TestTelegramRequest,
    TestTelegramResponse,
    ServiceProfileSchema,
    ServicesOverviewSchema,
    ApplyServicesRequest,
    ApplyServicesResponse,
    ApplyRuntimesRequest,
    ApplyRuntimesResponse,
    RuntimeVersionSchema,
    RuntimesOverviewSchema,
)
from controlbox.modules.platform.domain.entities import DEFAULT_SECRETS_CHECKLIST
from controlbox.modules.platform.infrastructure.panel_config import PanelConfigService
from controlbox.modules.platform.infrastructure.panel_operations import PanelOperationsService
from controlbox.modules.platform.infrastructure.panel_settings import PanelSettingsService
from controlbox.modules.platform.infrastructure.service_profiles import ServiceProfilesManager
from controlbox.modules.platform.infrastructure.runtime_catalog import RuntimeCatalogManager
from controlbox.shared.application.unit_of_work import UnitOfWork

logger = logging.getLogger("controlbox.platform.api")

router = APIRouter(prefix="/platform", tags=["platform"])

PLATFORM_ADMIN_ROLES = {"admin", "owner", "administrator"}

SECRET_LABELS = {
    "REDIS_PASSWORD": "Contraseña Redis",
    "REGISTRATION_INVITE_TOKEN": "Token de invitación de registro",
    "MYSQL_ADMIN_PASSWORD": "Contraseña admin MySQL",
    "MARIADB_ADMIN_PASSWORD": "Contraseña admin MariaDB",
    "MSSQL_ADMIN_PASSWORD": "Contraseña admin MSSQL",
    "GRAFANA_ADMIN_PASSWORD": "Contraseña admin Grafana",
    "SUPABASE_JWT_SECRET": "JWT Secret Supabase",
    "POWERDNS_API_KEY": "API Key PowerDNS",
}

SETUP_ITEMS = [
    ("configure_services", "Instalar paquetes de software"),
    ("configure_panel_access", "Configurar puerto y ruta del panel"),
    ("enable_totp", "Activar TOTP / MFA para administradores"),
    ("configure_domains", "Configurar dominios y SSL"),
    ("review_alert_thresholds", "Revisar umbrales de alertas de recursos"),
]


def _require_tenant(context: RequestContext) -> UUID:
    if not context.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant context required")
    return context.tenant_id


def _patch_setup_checklist(checklist: dict | None, **updates: bool) -> dict[str, bool]:
    return {**(checklist or {}), **updates}


def require_platform_admin():
    async def dependency(context: Annotated[RequestContext, Depends(get_current_context)]) -> RequestContext:
        if context.is_platform_admin:
            return context
        if not any(role in PLATFORM_ADMIN_ROLES for role in context.roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner or Administrator role required")
        return context

    return dependency


def _secrets_schema(status_map: dict[str, bool]) -> SecretsRotationSchema:
    items = [
        SecretRotationItemSchema(
            key=key,
            label=SECRET_LABELS.get(key, key),
            rotated=bool(status_map.get(key, False)),
            required=key in {
                "REDIS_PASSWORD",
                "REGISTRATION_INVITE_TOKEN",
                "GRAFANA_ADMIN_PASSWORD",
                "SUPABASE_JWT_SECRET",
                "POWERDNS_API_KEY",
            },
        )
        for key in DEFAULT_SECRETS_CHECKLIST
    ]
    required_items = [i for i in items if i.required]
    all_rotated = all(i.rotated for i in required_items)
    return SecretsRotationSchema(items=items, all_rotated=all_rotated, production_ready=all_rotated)


def _checklist_schema(checklist: dict[str, bool]) -> SetupChecklistSchema:
    items = [
        SetupChecklistItemSchema(key=key, label=label, completed=bool(checklist.get(key, False)))
        for key, label in SETUP_ITEMS
    ]
    completed = sum(1 for i in items if i.completed)
    return SetupChecklistSchema(
        items=items,
        completed_count=completed,
        total_count=len(items),
        production_ready=completed == len(items),
    )


def _alert_schema(alert) -> ResourceAlertSchema:
    return ResourceAlertSchema(
        id=str(alert.id),
        metric=alert.metric,
        severity=alert.severity,
        message=alert.message,
        current_value=alert.current_value,
        threshold_value=alert.threshold_value,
        is_acknowledged=alert.is_acknowledged,
        created_at=alert.created_at.isoformat() if alert.created_at else None,
    )


@router.get("/sysinfo", response_model=SystemInfoSchema)
async def get_system_info(
    _: Annotated[RequestContext, Depends(get_current_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SystemInfoSchema:
    profile = settings.controlbox_profile.upper()
    edition = "PRO" if profile in {"PROFESSIONAL", "ENTERPRISE", "PRO"} else "PRO"
    return SystemInfoSchema(
        version=resolve_controlbox_version(settings),
        os_label=settings.controlbox_os_label,
        profile=settings.controlbox_profile,
        edition=edition,
    )


@router.get("/panel-settings", response_model=PanelSettingsSchema)
async def get_panel_settings(
    context: Annotated[RequestContext, Depends(require_platform_admin())],
    _: Annotated[None, Depends(require_permission("platform.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PanelSettingsSchema:
    tenant_id = _require_tenant(context)
    platform_settings = await uow.tenant_platform_settings.get_or_create(tenant_id)
    view = PanelSettingsService(settings).build_view(platform_settings)
    return PanelSettingsSchema(**view)


@router.patch("/panel-settings", response_model=PanelSettingsSchema)
async def update_panel_settings(
    payload: UpdatePanelSettingsRequest,
    context: Annotated[RequestContext, Depends(require_platform_admin())],
    _: Annotated[None, Depends(require_permission("platform.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PanelSettingsSchema:
    tenant_id = _require_tenant(context)
    service = PanelSettingsService(settings)
    platform_settings = await uow.tenant_platform_settings.get_or_create(tenant_id)

    service.apply_preferences(
        platform_settings,
        panel_alias=payload.panel_alias,
        session_timeout_hours=payload.session_timeout_hours,
        ipv6_enabled=payload.ipv6_enabled,
        offline_mode=payload.offline_mode,
        cdn_proxy=payload.cdn_proxy,
        auto_fetch_favicon=payload.auto_fetch_favicon,
        auto_backup_panel=payload.auto_backup_panel,
        auto_backup_retention=payload.auto_backup_retention,
        server_ip=payload.server_ip,
        site_monitor_enabled=payload.site_monitor_enabled,
        cpu_threshold_percent=payload.cpu_threshold_percent,
        memory_threshold_percent=payload.memory_threshold_percent,
        disk_threshold_percent=payload.disk_threshold_percent,
        alert_cooldown_minutes=payload.alert_cooldown_minutes,
        telegram_alerts_enabled=payload.telegram_alerts_enabled,
        telegram_bot_token=payload.telegram_bot_token,
        telegram_chat_id=payload.telegram_chat_id,
        sidebar_hidden_items=payload.sidebar_hidden_items,
    )

    if payload.panel_port is not None or payload.panel_base_path is not None:
        await PanelConfigService(settings).update_config(
            panel_port=payload.panel_port,
            panel_base_path=payload.panel_base_path,
        )

    if payload.default_site_folder is not None or payload.default_backup_folder is not None:
        await service.update_host_paths(
            default_site_folder=payload.default_site_folder,
            default_backup_folder=payload.default_backup_folder,
        )

    await uow.tenant_platform_settings.save(platform_settings)
    await uow.commit()
    view = service.build_view(platform_settings)
    return PanelSettingsSchema(**view)


@router.post("/panel-settings/test-telegram", response_model=TestTelegramResponse)
async def test_telegram_alerts(
    payload: TestTelegramRequest,
    context: Annotated[RequestContext, Depends(require_platform_admin())],
    _: Annotated[None, Depends(require_permission("platform.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TestTelegramResponse:
    tenant_id = _require_tenant(context)
    service = PanelSettingsService(settings)
    platform_settings = await uow.tenant_platform_settings.get_or_create(tenant_id)
    ok, message = await service.test_telegram(
        platform_settings,
        bot_token=payload.telegram_bot_token,
        chat_id=payload.telegram_chat_id,
    )
    return TestTelegramResponse(success=ok, message=message)


@router.post("/panel-settings/sync-time", response_model=PanelActionResponse)
async def sync_panel_server_time(
    _: Annotated[RequestContext, Depends(require_platform_admin())],
    __: Annotated[None, Depends(require_permission("platform.manage"))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PanelActionResponse:
    server_time = await PanelSettingsService(settings).sync_server_time()
    return PanelActionResponse(
        success=True,
        message="Server time synchronized",
        server_time=ServerTimeSchema(**server_time),
    )


@router.post("/panel-settings/shutdown-panel", response_model=PanelActionResponse)
async def shutdown_panel_service(
    _: Annotated[RequestContext, Depends(require_platform_admin())],
    __: Annotated[None, Depends(require_permission("platform.manage"))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PanelActionResponse:
    result = await PanelSettingsService(settings).shutdown_panel_only()
    return PanelActionResponse(success=result["success"], message=result["message"])


@router.get("/overview", response_model=PlatformOverviewSchema)
async def get_platform_overview(
    context: Annotated[RequestContext, Depends(require_platform_admin())],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PlatformOverviewSchema:
    tenant_id = _require_tenant(context)
    panel_service = PanelConfigService(settings)
    panel = panel_service.get_config()
    platform_settings = await uow.tenant_platform_settings.get_or_create(tenant_id)
    active_count = await uow.resource_alerts.count_active(tenant_id)

    checklist = _checklist_schema(platform_settings.setup_checklist)
    secrets = _secrets_schema(platform_settings.secrets_rotation_status)
    return PlatformOverviewSchema(
        panel=PanelConfigSchema(**panel),
        alert_thresholds=AlertThresholdsSchema(
            cpu_threshold_percent=platform_settings.cpu_threshold_percent,
            memory_threshold_percent=platform_settings.memory_threshold_percent,
            disk_threshold_percent=platform_settings.disk_threshold_percent,
            alerts_enabled=platform_settings.alerts_enabled,
            alert_cooldown_minutes=platform_settings.alert_cooldown_minutes,
        ),
        secrets_rotation=secrets,
        setup_checklist=checklist,
        active_alerts_count=active_count,
        is_production_ready=checklist.production_ready,
    )


@router.get("/panel", response_model=PanelConfigSchema)
async def get_panel_config(
    _: Annotated[None, Depends(require_permission("platform.read"))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PanelConfigSchema:
    return PanelConfigSchema(**PanelConfigService(settings).get_config())


@router.patch("/panel", response_model=UpdatePanelConfigResponse)
async def update_panel_config(
    payload: UpdatePanelConfigRequest,
    _: Annotated[RequestContext, Depends(require_platform_admin())],
    __: Annotated[None, Depends(require_permission("platform.manage"))],
    settings: Annotated[Settings, Depends(get_settings)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> UpdatePanelConfigResponse:
    if payload.panel_port is None and payload.panel_base_path is None:
        raise HTTPException(status_code=400, detail="No changes provided")
    try:
        result = await PanelConfigService(settings).update_config(
            panel_port=payload.panel_port,
            panel_base_path=payload.panel_base_path,
        )
        tenant_id = _.tenant_id
        if tenant_id:
            platform_settings = await uow.tenant_platform_settings.get_or_create(tenant_id)
            platform_settings.setup_checklist = _patch_setup_checklist(
                platform_settings.setup_checklist, configure_panel_access=True
            )
            await uow.tenant_platform_settings.save(platform_settings)
            await uow.commit()
        return UpdatePanelConfigResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/alert-thresholds", response_model=AlertThresholdsSchema)
async def update_alert_thresholds(
    payload: AlertThresholdsSchema,
    context: Annotated[RequestContext, Depends(require_platform_admin())],
    _: Annotated[None, Depends(require_permission("platform.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> AlertThresholdsSchema:
    tenant_id = _require_tenant(context)
    settings = await uow.tenant_platform_settings.get_or_create(tenant_id)
    settings.cpu_threshold_percent = payload.cpu_threshold_percent
    settings.memory_threshold_percent = payload.memory_threshold_percent
    settings.disk_threshold_percent = payload.disk_threshold_percent
    settings.alerts_enabled = payload.alerts_enabled
    settings.alert_cooldown_minutes = payload.alert_cooldown_minutes
    settings.setup_checklist = _patch_setup_checklist(
        settings.setup_checklist, review_alert_thresholds=True
    )
    await uow.tenant_platform_settings.save(settings)
    await uow.commit()
    return payload


@router.get("/alerts", response_model=list[ResourceAlertSchema])
async def list_resource_alerts(
    context: Annotated[RequestContext, Depends(require_platform_admin())],
    _: Annotated[None, Depends(require_permission("platform.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    active_only: bool = True,
) -> list[ResourceAlertSchema]:
    tenant_id = _require_tenant(context)
    alerts = (
        await uow.resource_alerts.list_active(tenant_id)
        if active_only
        else await uow.resource_alerts.list_recent(tenant_id)
    )
    return [_alert_schema(a) for a in alerts]


@router.post("/alerts/{alert_id}/acknowledge", response_model=ResourceAlertSchema)
async def acknowledge_alert(
    alert_id: UUID,
    context: Annotated[RequestContext, Depends(require_platform_admin())],
    _: Annotated[None, Depends(require_permission("platform.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ResourceAlertSchema:
    tenant_id = _require_tenant(context)
    alert = await uow.resource_alerts.get_by_id(alert_id, tenant_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    from controlbox.shared.domain.base import utc_now

    alert.is_acknowledged = True
    alert.acknowledged_at = utc_now()
    await uow.resource_alerts.save(alert)
    await uow.commit()
    return _alert_schema(alert)


@router.post("/secrets/acknowledge", response_model=SecretsRotationSchema)
async def acknowledge_secret_rotation(
    payload: AcknowledgeSecretRequest,
    context: Annotated[RequestContext, Depends(require_platform_admin())],
    _: Annotated[None, Depends(require_permission("platform.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SecretsRotationSchema:
    if payload.secret_key not in DEFAULT_SECRETS_CHECKLIST:
        raise HTTPException(status_code=400, detail="Unknown secret key")
    tenant_id = _require_tenant(context)
    settings = await uow.tenant_platform_settings.get_or_create(tenant_id)
    settings.secrets_rotation_status = {
        **settings.secrets_rotation_status,
        payload.secret_key: True,
    }
    required = [k for k in DEFAULT_SECRETS_CHECKLIST if k in {
        "REDIS_PASSWORD", "REGISTRATION_INVITE_TOKEN",
        "GRAFANA_ADMIN_PASSWORD", "SUPABASE_JWT_SECRET", "POWERDNS_API_KEY",
    }]
    if all(settings.secrets_rotation_status.get(k) for k in required):
        pass  # secrets review is optional; no longer blocks production checklist
    await uow.tenant_platform_settings.save(settings)
    await uow.commit()
    return _secrets_schema(settings.secrets_rotation_status)


@router.post("/secrets/confirm-reviewed", response_model=SecretsRotationSchema)
async def confirm_secrets_reviewed(
    context: Annotated[RequestContext, Depends(require_platform_admin())],
    _: Annotated[None, Depends(require_permission("platform.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SecretsRotationSchema:
    tenant_id = _require_tenant(context)
    settings = await uow.tenant_platform_settings.get_or_create(tenant_id)
    merged = {**settings.secrets_rotation_status}
    for key in DEFAULT_SECRETS_CHECKLIST:
        merged[key] = True
    settings.secrets_rotation_status = merged
    await uow.tenant_platform_settings.save(settings)
    await uow.commit()
    return _secrets_schema(settings.secrets_rotation_status)


@router.get("/services", response_model=ServicesOverviewSchema)
async def get_service_profiles(
    _: Annotated[RequestContext, Depends(require_platform_admin())],
    __: Annotated[None, Depends(require_permission("platform.read"))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ServicesOverviewSchema:
    overview = await ServiceProfilesManager(settings).get_overview()
    return ServicesOverviewSchema(
        can_manage=overview.can_manage,
        enabled_profiles=overview.enabled_profiles,
        message=overview.message,
        services=[
            ServiceProfileSchema(
                id=s.id,
                profile=s.profile,
                name=s.name,
                category=s.category,
                description=s.description,
                enabled=s.enabled,
                running=s.running,
                requires=list(s.requires),
            )
            for s in overview.services
        ],
    )


@router.post("/services/apply", response_model=ApplyServicesResponse)
async def apply_service_profiles(
    payload: ApplyServicesRequest,
    context: Annotated[RequestContext, Depends(require_platform_admin())],
    _: Annotated[None, Depends(require_permission("platform.manage"))],
    settings: Annotated[Settings, Depends(get_settings)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ApplyServicesResponse:
    try:
        manager = ServiceProfilesManager(settings)
        ok, message, profiles = await manager.apply_profiles(payload.profiles)
        if ok:
            tenant_id = _require_tenant(context)
            platform_settings = await uow.tenant_platform_settings.get_or_create(tenant_id)
            platform_settings.setup_checklist = _patch_setup_checklist(
                platform_settings.setup_checklist, configure_services=True
            )
            await uow.tenant_platform_settings.save(platform_settings)
            await uow.commit()
        return ApplyServicesResponse(success=ok, message=message, enabled_profiles=profiles)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("apply_service_profiles failed")
        return ApplyServicesResponse(success=False, message=str(exc), enabled_profiles=[])


@router.post("/services/supabase/ensure", response_model=ApplyServicesResponse)
async def ensure_supabase_service(
    context: Annotated[RequestContext, Depends(require_platform_admin())],
    _: Annotated[None, Depends(require_permission("platform.manage"))],
    settings: Annotated[Settings, Depends(get_settings)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ApplyServicesResponse:
    """Enable Supabase profile (and dependencies) and start containers."""
    manager = ServiceProfilesManager(settings)
    current = manager._read_enabled_profiles()
    profiles = manager._normalize_profiles(list(set(current) | {"databases", "backups", "supabase"}))
    ok, message, applied = await manager.apply_profiles(profiles)
    if ok:
        ok_sb, msg_sb = await manager._ensure_supabase_stack(profiles, wait_seconds=30)
        if msg_sb:
            message = f"{message} {msg_sb}".strip()
        if not ok_sb:
            ok = False
            message = msg_sb or message
    if ok:
        tenant_id = _require_tenant(context)
        platform_settings = await uow.tenant_platform_settings.get_or_create(tenant_id)
        platform_settings.setup_checklist = _patch_setup_checklist(
            platform_settings.setup_checklist, configure_services=True
        )
        await uow.tenant_platform_settings.save(platform_settings)
        await uow.commit()
    return ApplyServicesResponse(success=ok, message=message, enabled_profiles=applied)


@router.get("/runtimes", response_model=RuntimesOverviewSchema)
async def get_runtime_profiles(
    _: Annotated[RequestContext, Depends(require_platform_admin())],
    __: Annotated[None, Depends(require_permission("platform.read"))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RuntimesOverviewSchema:
    overview = await RuntimeCatalogManager(settings).get_overview()
    return RuntimesOverviewSchema(
        can_manage=overview.can_manage,
        enabled_runtimes=overview.enabled_runtimes,
        message=overview.message,
        runtimes=[
            RuntimeVersionSchema(
                id=r.id,
                runtime=r.runtime,
                version=r.version,
                name=r.name,
                category=r.category,
                image=r.image,
                enabled=r.enabled,
                installed=r.installed,
            )
            for r in overview.runtimes
        ],
    )


@router.post("/runtimes/apply", response_model=ApplyRuntimesResponse)
async def apply_runtime_profiles(
    payload: ApplyRuntimesRequest,
    context: Annotated[RequestContext, Depends(require_platform_admin())],
    _: Annotated[None, Depends(require_permission("platform.manage"))],
    settings: Annotated[Settings, Depends(get_settings)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ApplyRuntimesResponse:
    try:
        manager = RuntimeCatalogManager(settings)
        ok, message, runtimes = await manager.apply_runtimes(payload.runtimes)
        if ok:
            tenant_id = _require_tenant(context)
            platform_settings = await uow.tenant_platform_settings.get_or_create(tenant_id)
            platform_settings.setup_checklist = _patch_setup_checklist(
                platform_settings.setup_checklist, configure_services=True
            )
            await uow.tenant_platform_settings.save(platform_settings)
            await uow.commit()
        return ApplyRuntimesResponse(success=ok, message=message, enabled_runtimes=runtimes)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("apply_runtime_profiles failed")
        return ApplyRuntimesResponse(success=False, message=str(exc), enabled_runtimes=[])


@router.patch("/setup-checklist", response_model=SetupChecklistSchema)
async def update_setup_checklist(
    payload: UpdateSetupChecklistRequest,
    context: Annotated[RequestContext, Depends(require_platform_admin())],
    _: Annotated[None, Depends(require_permission("platform.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SetupChecklistSchema:
    valid_keys = {key for key, _ in SETUP_ITEMS}
    if payload.key not in valid_keys:
        raise HTTPException(status_code=400, detail="Invalid checklist key")
    tenant_id = _require_tenant(context)
    settings = await uow.tenant_platform_settings.get_or_create(tenant_id)
    settings.setup_checklist = _patch_setup_checklist(
        settings.setup_checklist, **{payload.key: payload.completed}
    )
    await uow.tenant_platform_settings.save(settings)
    await uow.commit()
    return _checklist_schema(settings.setup_checklist)


@router.post("/operations/restart-panel", response_model=OperationResultSchema)
async def restart_panel(
    _: Annotated[RequestContext, Depends(require_platform_admin())],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OperationResultSchema:
    result = await PanelOperationsService(settings).restart_panel()
    return OperationResultSchema(success=result.success, message=result.message, detail=result.detail)


@router.post("/operations/fix", response_model=OperationResultSchema)
async def fix_stack(
    _: Annotated[RequestContext, Depends(require_platform_admin())],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OperationResultSchema:
    result = await PanelOperationsService(settings).fix_stack()
    return OperationResultSchema(success=result.success, message=result.message, detail=result.detail)


@router.get("/operations/update-check", response_model=UpdateCheckSchema)
async def check_for_updates(
    _: Annotated[RequestContext, Depends(require_platform_admin())],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UpdateCheckSchema:
    result = await PanelOperationsService(settings).check_updates()
    return UpdateCheckSchema(
        current_version=result.current_version,
        latest_version=result.latest_version,
        update_available=result.update_available,
        source=result.source,
        release_url=result.release_url,
        tarball_url=result.tarball_url,
    )


@router.post("/operations/update", response_model=OperationResultSchema)
async def apply_update(
    _: Annotated[RequestContext, Depends(require_platform_admin())],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OperationResultSchema:
    result = await PanelOperationsService(settings).apply_update()
    return OperationResultSchema(success=result.success, message=result.message, detail=result.detail)
