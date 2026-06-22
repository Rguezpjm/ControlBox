from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from controlbox.version import __version__


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="ControlBox", alias="APP_NAME")
    app_env: str = Field(default="production", alias="APP_ENV")
    app_debug: bool = Field(default=False, alias="APP_DEBUG")
    app_secret_key: str = Field(alias="APP_SECRET_KEY")
    app_api_prefix: str = Field(default="/api/v1", alias="APP_API_PREFIX")

    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="controlbox", alias="POSTGRES_DB")
    postgres_user: str = Field(default="controlbox", alias="POSTGRES_USER")
    postgres_password: str = Field(alias="POSTGRES_PASSWORD")

    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_password: str = Field(default="", alias="REDIS_PASSWORD")
    redis_db: int = Field(default=0, alias="REDIS_DB")

    jwt_access_token_expire_minutes: int = Field(default=15, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    jwt_refresh_token_expire_days: int = Field(default=7, alias="JWT_REFRESH_TOKEN_EXPIRE_DAYS")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")

    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    sites_base_path: str = Field(default="/var/lib/controlbox/sites", alias="SITES_BASE_PATH")
    mysql_host: str = Field(default="mysql", alias="MYSQL_HOST")
    mysql_port: int = Field(default=3306, alias="MYSQL_PORT")
    mysql_admin_user: str = Field(default="root", alias="MYSQL_ADMIN_USER")
    mysql_admin_password: str = Field(default="root", alias="MYSQL_ADMIN_PASSWORD")

    mariadb_host: str = Field(default="mariadb", alias="MARIADB_HOST")
    mariadb_port: int = Field(default=3306, alias="MARIADB_PORT")
    mariadb_admin_user: str = Field(default="root", alias="MARIADB_ADMIN_USER")
    mariadb_admin_password: str = Field(default="root", alias="MARIADB_ADMIN_PASSWORD")

    managed_postgres_host: str = Field(default="managed-postgres", alias="MANAGED_POSTGRES_HOST")
    managed_postgres_port: int = Field(default=5432, alias="MANAGED_POSTGRES_PORT")
    managed_postgres_admin_user: str = Field(default="postgres", alias="MANAGED_POSTGRES_ADMIN_USER")
    managed_postgres_admin_password: str = Field(default="postgres", alias="MANAGED_POSTGRES_ADMIN_PASSWORD")

    supabase_db_host: str = Field(default="supabase-db", alias="SUPABASE_DB_HOST")
    supabase_db_port: int = Field(default=5432, alias="SUPABASE_DB_PORT")
    supabase_db_admin_user: str = Field(default="postgres", alias="SUPABASE_DB_ADMIN_USER")
    supabase_db_admin_password: str = Field(default="postgres", alias="SUPABASE_DB_ADMIN_PASSWORD")
    supabase_jwt_secret: str = Field(default="your-super-secret-jwt-token", alias="SUPABASE_JWT_SECRET")
    supabase_url: str = Field(default="http://supabase-kong:8000", alias="SUPABASE_URL")
    supabase_storage_url: str = Field(default="http://supabase-storage:5000", alias="SUPABASE_STORAGE_URL")
    supabase_studio_url: str = Field(default="http://supabase-studio:3000", alias="SUPABASE_STUDIO_URL")
    supabase_anon_key: str = Field(default="", alias="SUPABASE_ANON_KEY")
    supabase_service_key: str = Field(default="", alias="SUPABASE_SERVICE_KEY")
    mssql_host: str = Field(default="mssql", alias="MSSQL_HOST")
    mssql_port: int = Field(default=1433, alias="MSSQL_PORT")
    mssql_admin_user: str = Field(default="sa", alias="MSSQL_ADMIN_USER")
    mssql_admin_password: str = Field(default="YourStrong!Passw0rd", alias="MSSQL_ADMIN_PASSWORD")

    database_backups_path: str = Field(default="/var/lib/controlbox/backups/databases", alias="DATABASE_BACKUPS_PATH")
    backups_base_path: str = Field(default="/var/lib/controlbox/backups", alias="BACKUPS_BASE_PATH")

    powerdns_api_url: str = Field(default="http://powerdns:8081", alias="POWERDNS_API_URL")
    powerdns_api_key: str = Field(default="changeme", alias="POWERDNS_API_KEY")
    powerdns_server_id: str = Field(default="localhost", alias="POWERDNS_SERVER_ID")
    powerdns_default_ttl: int = Field(default=3600, alias="POWERDNS_DEFAULT_TTL")
    powerdns_nameservers: str = Field(default="ns1.controlbox.io,ns2.controlbox.io", alias="POWERDNS_NAMESERVERS")

    pureftpd_enabled: bool = Field(default=True, alias="PUREFTPD_ENABLED")
    pureftpd_host: str = Field(default="localhost", alias="PUREFTPD_HOST")
    pureftpd_port: int = Field(default=21, alias="PUREFTPD_PORT")
    pureftpd_protocol: str = Field(default="ftp", alias="PUREFTPD_PROTOCOL")
    pureftpd_public_host: str = Field(default="localhost", alias="PUREFTPD_PUBLIC_HOST")
    pureftpd_passive_port_min: int = Field(default=30000, alias="PUREFTPD_PASSIVE_MIN")
    pureftpd_passive_port_max: int = Field(default=30009, alias="PUREFTPD_PASSIVE_MAX")
    pureftpd_tls: int = Field(default=0, alias="PUREFTPD_TLS")
    pureftpd_container: str = Field(default="controlbox-pureftpd", alias="PUREFTPD_CONTAINER")
    pureftpd_use_docker: bool = Field(default=True, alias="PUREFTPD_USE_DOCKER")
    pureftpd_passwd_file: str = Field(default="/etc/pure-ftpd/pureftpd.passwd", alias="PUREFTPD_PASSWD_FILE")
    pureftpd_log_path: str = Field(default="/var/log/pure-ftpd/transfer.log", alias="PUREFTPD_LOG_PATH")
    pureftpd_virtual_uid: int = Field(default=1000, alias="PUREFTPD_VIRTUAL_UID")
    pureftpd_virtual_gid: int = Field(default=1000, alias="PUREFTPD_VIRTUAL_GID")

    monitoring_interval_seconds: int = Field(default=5, alias="MONITORING_INTERVAL_SECONDS")
    monitoring_use_docker: bool = Field(default=True, alias="MONITORING_USE_DOCKER")
    host_proc_path: str = Field(default="", alias="HOST_PROC")
    host_root_path: str = Field(default="", alias="HOST_ROOT")

    security_enabled: bool = Field(default=True, alias="SECURITY_ENABLED")
    security_waf_enabled: bool = Field(default=True, alias="SECURITY_WAF_ENABLED")
    security_brute_force_enabled: bool = Field(default=True, alias="SECURITY_BRUTE_FORCE_ENABLED")
    security_brute_force_max_attempts: int = Field(default=5, alias="SECURITY_BRUTE_FORCE_MAX_ATTEMPTS")
    security_brute_force_block_seconds: int = Field(default=3600, alias="SECURITY_BRUTE_FORCE_BLOCK_SECONDS")
    security_rate_limit_login: int = Field(default=10, alias="SECURITY_RATE_LIMIT_LOGIN")
    security_rate_limit_api: int = Field(default=300, alias="SECURITY_RATE_LIMIT_API")
    security_trust_proxy: bool = Field(default=True, alias="SECURITY_TRUST_PROXY")
    security_csp: str = Field(
        default="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' ws: wss:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
        alias="SECURITY_CSP",
    )
    webauthn_rp_id: str = Field(default="localhost", alias="WEBAUTHN_RP_ID")
    webauthn_rp_name: str = Field(default="ControlBox", alias="WEBAUTHN_RP_NAME")
    webauthn_origin: str = Field(default="http://localhost:3000", alias="WEBAUTHN_ORIGIN")
    crowdsec_enabled: bool = Field(default=False, alias="CROWDSEC_ENABLED")
    crowdsec_lapi_url: str = Field(default="http://crowdsec:8080", alias="CROWDSEC_LAPI_URL")

    registration_enabled: bool = Field(default=True, alias="REGISTRATION_ENABLED")
    registration_invite_token: str = Field(default="", alias="REGISTRATION_INVITE_TOKEN")
    installer_bootstrap_token: str = Field(default="", alias="INSTALLER_BOOTSTRAP_TOKEN")
    security_csrf_enabled: bool = Field(default=True, alias="SECURITY_CSRF_ENABLED")
    cookie_secure: bool | None = Field(default=None, alias="COOKIE_SECURE")

    uvicorn_workers: int = Field(default=1, alias="UVICORN_WORKERS")
    db_pool_size: int = Field(default=10, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=5, alias="DB_MAX_OVERFLOW")
    background_tasks_enabled: bool = Field(default=True, alias="BACKGROUND_TASKS_ENABLED")
    security_rate_limit_global: int = Field(default=600, alias="SECURITY_RATE_LIMIT_GLOBAL")

    docker_host: str = Field(
        default="",
        alias="DOCKER_HOST",
        description="Docker API endpoint (e.g. tcp://docker-socket-proxy:2375). Empty uses CLI default.",
    )

    platform_config_dir: str = Field(default="/etc/controlbox", alias="PLATFORM_CONFIG_DIR")
    controlbox_install_dir: str = Field(default="/opt/controlbox", alias="CONTROLBOX_INSTALL_DIR")
    controlbox_data_dir: str = Field(default="/var/lib/controlbox", alias="CONTROLBOX_DATA_DIR")
    panel_port: int = Field(default=8475, alias="PANEL_PORT")
    panel_base_path: str = Field(default="", alias="PANEL_BASE_PATH")
    controlbox_version: str = Field(default=__version__, alias="CONTROLBOX_VERSION")
    controlbox_profile: str = Field(default="standard", alias="CONTROLBOX_PROFILE")
    controlbox_os_label: str = Field(default="Linux", alias="CONTROLBOX_OS_LABEL")
    controlbox_install_url: str = Field(default="https://install.grodtech.com", alias="CONTROLBOX_INSTALL_URL")
    controlbox_github_repo: str = Field(default="Rguezpjm/ControlBox", alias="CONTROLBOX_GITHUB_REPO")
    controlbox_server_ip: str = Field(default="", alias="CONTROLBOX_SERVER_IP")
    controlbox_enabled_profiles: str = Field(default="databases,backups", alias="CONTROLBOX_ENABLED_PROFILES")
    controlbox_enabled_runtimes: str = Field(
        default="php:8.2,php:8.3,nodejs:22,python:3.13,flutter:3.44.2",
        alias="CONTROLBOX_ENABLED_RUNTIMES",
    )

    celery_broker_url: str = Field(default="redis://localhost:6379/1", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/2", alias="CELERY_RESULT_BACKEND")

    @property
    def powerdns_nameservers_list(self) -> list[str]:
        return [ns.strip() for ns in self.powerdns_nameservers.split(",") if ns.strip()]

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def use_secure_cookies(self) -> bool:
        """Secure cookies require HTTPS. HTTP panel installs (IP:PORT) must use False."""
        if self.cookie_secure is not None:
            return self.cookie_secure
        origins = self.cors_origins_list
        if not origins:
            return False
        return all(origin.lower().startswith("https://") for origin in origins)


@lru_cache
def get_settings() -> Settings:
    return Settings()
