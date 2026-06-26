from controlbox.config.settings import Settings
from controlbox.modules.joomla.application.queries import JoomlaSiteResponse
from controlbox.modules.joomla.domain.entities import JoomlaSite
from controlbox.modules.joomla.infrastructure.site_access import build_site_access_info


def to_joomla_site_response(site: JoomlaSite, settings: Settings | None = None) -> JoomlaSiteResponse:
    access = build_site_access_info(site, settings) if settings else None
    return JoomlaSiteResponse(
        id=site.id,
        tenant_id=site.tenant_id,
        name=site.name,
        domain=site.domain,
        status=site.status.value,
        php_version=site.php_version,
        joomla_version=site.joomla_version,
        url=site.url,
        admin_user=site.admin_user,
        admin_email=site.admin_email,
        ssl_enabled=site.ssl_enabled,
        ssl_status=site.ssl_status.value,
        maintenance_mode=site.maintenance_mode,
        disk_used_mb=site.disk_used_mb,
        db_size_mb=site.db_size_mb,
        is_staging=site.is_staging,
        parent_site_id=site.parent_site_id,
        error_message=site.error_message,
        task_id=site.task_id,
        access_info=access,
        created_at=site.created_at,
        updated_at=site.updated_at,
    )
