from controlbox.modules.wordpress.domain.entities import (
    WordPressBackup,
    WordPressBackupStatus,
    WordPressSite,
    WordPressSslStatus,
    WordPressStatus,
)
from controlbox.modules.wordpress.infrastructure.models import WordPressBackupModel, WordPressSiteModel


def site_to_entity(model: WordPressSiteModel) -> WordPressSite:
    return WordPressSite(
        id=model.id,
        tenant_id=model.tenant_id,
        name=model.name,
        domain=model.domain,
        status=WordPressStatus(model.status),
        php_version=model.php_version,
        wordpress_version=model.wordpress_version,
        url=model.url,
        admin_user=model.admin_user,
        admin_email=model.admin_email,
        managed_database_id=model.managed_database_id,
        database_user_id=model.database_user_id,
        nginx_container_name=model.nginx_container_name,
        php_container_name=model.php_container_name,
        site_path=model.site_path,
        ssl_enabled=model.ssl_enabled,
        ssl_status=WordPressSslStatus(model.ssl_status),
        maintenance_mode=model.maintenance_mode,
        disk_used_mb=model.disk_used_mb,
        db_size_mb=model.db_size_mb,
        parent_site_id=model.parent_site_id,
        is_staging=model.is_staging,
        settings=model.settings or {},
        error_message=model.error_message,
        task_id=model.task_id,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def site_to_model(entity: WordPressSite) -> WordPressSiteModel:
    return WordPressSiteModel(
        id=entity.id,
        tenant_id=entity.tenant_id,
        name=entity.name,
        domain=entity.domain,
        status=entity.status.value,
        php_version=entity.php_version,
        wordpress_version=entity.wordpress_version,
        url=entity.url,
        admin_user=entity.admin_user,
        admin_email=entity.admin_email,
        managed_database_id=entity.managed_database_id,
        database_user_id=entity.database_user_id,
        nginx_container_name=entity.nginx_container_name,
        php_container_name=entity.php_container_name,
        site_path=entity.site_path,
        ssl_enabled=entity.ssl_enabled,
        ssl_status=entity.ssl_status.value,
        maintenance_mode=entity.maintenance_mode,
        disk_used_mb=entity.disk_used_mb,
        db_size_mb=entity.db_size_mb,
        parent_site_id=entity.parent_site_id,
        is_staging=entity.is_staging,
        settings=entity.settings,
        error_message=entity.error_message,
        task_id=entity.task_id,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def backup_to_entity(model: WordPressBackupModel) -> WordPressBackup:
    return WordPressBackup(
        id=model.id,
        site_id=model.site_id,
        tenant_id=model.tenant_id,
        name=model.name,
        status=WordPressBackupStatus(model.status),
        file_path=model.file_path,
        size_mb=model.size_mb,
        checksum=model.checksum,
        includes_database=model.includes_database,
        includes_files=model.includes_files,
        error_message=model.error_message,
        completed_at=model.completed_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def backup_to_model(entity: WordPressBackup) -> WordPressBackupModel:
    return WordPressBackupModel(
        id=entity.id,
        site_id=entity.site_id,
        tenant_id=entity.tenant_id,
        name=entity.name,
        status=entity.status.value if hasattr(entity.status, "value") else entity.status,
        file_path=entity.file_path,
        size_mb=entity.size_mb,
        checksum=entity.checksum,
        includes_database=entity.includes_database,
        includes_files=entity.includes_files,
        error_message=entity.error_message,
        completed_at=entity.completed_at,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )
