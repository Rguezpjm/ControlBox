import asyncio
import hashlib
import os
import secrets
import shutil
import tarfile
from pathlib import Path
from uuid import UUID

from controlbox.config.settings import Settings
from controlbox.modules.databases.domain.entities import DatabaseEngineType, DatabaseStatus
from controlbox.modules.databases.infrastructure.engine_adapters import compute_checksum, generate_password
from controlbox.modules.databases.infrastructure.provisioner import (
    DatabaseProvisioner,
    build_database_user,
    build_managed_database,
)
from controlbox.modules.supabase.infrastructure.crypto import SecretEncryptor
from controlbox.modules.wordpress.domain.entities import WordPressBackup, WordPressSite
from controlbox.shared.infrastructure.docker.env import docker_subprocess_env, validate_container_name


def _generate_wp_salts() -> dict[str, str]:
    keys = [
        "AUTH_KEY", "SECURE_AUTH_KEY", "LOGGED_IN_KEY", "NONCE_KEY",
        "AUTH_SALT", "SECURE_AUTH_SALT", "LOGGED_IN_SALT", "NONCE_SALT",
    ]
    return {key: secrets.token_urlsafe(64) for key in keys}


def _render_wp_config(
    db_name: str,
    db_user: str,
    db_password: str,
    db_host: str,
    table_prefix: str,
    salts: dict[str, str],
) -> str:
    salt_lines = "\n".join(f"define('{k}', '{v}');" for k, v in salts.items())
    return f"""<?php
define('DB_NAME', '{db_name}');
define('DB_USER', '{db_user}');
define('DB_PASSWORD', '{db_password}');
define('DB_HOST', '{db_host}');
define('DB_CHARSET', 'utf8mb4');
define('DB_COLLATE', '');
$table_prefix = '{table_prefix}';
{salt_lines}
define('WP_DEBUG', false);
define('FS_METHOD', 'direct');
define('DISALLOW_FILE_EDIT', true);
if ( ! defined( 'ABSPATH' ) ) {{
    define( 'ABSPATH', __DIR__ . '/' );
}}
require_once ABSPATH . 'wp-settings.php';
"""


def _render_nginx_conf() -> str:
    return """server {
    listen 80;
    server_name _;
    root /var/www/html;
    index index.php index.html;
    client_max_body_size 128M;

    location / {
        try_files $uri $uri/ /index.php?$args;
    }

    location ~ \\.php$ {
        fastcgi_pass php:9000;
        fastcgi_index index.php;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        include fastcgi_params;
        fastcgi_read_timeout 300;
    }

    location ~ /\\.ht {
        deny all;
    }

    location = /favicon.ico {
        log_not_found off;
        access_log off;
    }
}
"""


def _render_compose(
    nginx_name: str,
    php_name: str,
    php_image: str,
    php_version: str,
    domain: str,
    router_name: str,
    ssl_enabled: bool,
) -> str:
    tls_labels = ""
    if ssl_enabled:
        tls_labels = f"""
      - "traefik.http.routers.{router_name}.tls=true"
      - "traefik.http.routers.{router_name}.tls.certresolver=letsencrypt"
"""
    return f"""services:
  nginx:
    image: nginx:1.27-alpine
    container_name: {nginx_name}
    restart: unless-stopped
    volumes:
      - ./wordpress:/var/www/html:ro
      - ./nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - php
    networks:
      - controlbox
      - wp_internal
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.{router_name}.rule=Host(`{domain}`)"
      - "traefik.http.routers.{router_name}.entrypoints=websecure"
      - "traefik.http.services.{router_name}.loadbalancer.server.port=80"
      - "controlbox.wordpress=true"
      - "controlbox.logs.enabled=true"
{tls_labels}
  php:
    image: {php_image}
    container_name: {php_name}
    restart: unless-stopped
    volumes:
      - ./wordpress:/var/www/html
    networks:
      - controlbox
      - wp_internal
    user: "33:33"

  wp-cli:
    image: wordpress:cli-php{php_version}
    profiles: [cli]
    volumes:
      - ./wordpress:/var/www/html
    networks:
      - controlbox
      - wp_internal
    user: "33:33"
    working_dir: /var/www/html

networks:
  controlbox:
    external: true
  wp_internal:
    driver: bridge
"""


class WordPressProvisioner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._db = DatabaseProvisioner(settings)
        self._crypto = SecretEncryptor(settings)

    def get_site_path(self, tenant_id: UUID, site_id: UUID) -> Path:
        return Path(self._settings.sites_base_path) / str(tenant_id) / "wordpress" / str(site_id)

    def get_backup_path(self, tenant_id: UUID, site_id: UUID, backup_id: UUID) -> Path:
        path = Path(self._settings.backups_base_path) / str(tenant_id) / "wordpress" / str(site_id)
        path.mkdir(parents=True, exist_ok=True)
        return path / f"{backup_id}.tar.gz"

    async def provision_database(
        self,
        tenant_id: UUID,
        site_id: UUID,
    ) -> tuple[UUID, UUID, str, str, str]:
        db_slug = f"wp_{site_id.hex[:8]}"
        database_name = f"db_{str(tenant_id).split('-')[0]}_{db_slug}"[:63]
        database = build_managed_database(
            tenant_id=tenant_id,
            name=db_slug,
            engine=DatabaseEngineType.MYSQL,
            host=self._settings.mysql_host,
            port=self._settings.mysql_port,
            database_name=database_name,
            charset="utf8mb4",
            max_connections=50,
        )
        await self._db.provision_database(database)
        if database.status != DatabaseStatus.ACTIVE:
            raise RuntimeError("Failed to provision MySQL database")

        db_user_name = f"u_{str(tenant_id).split('-')[0]}_{db_slug}"[:32]
        plain_password = generate_password()
        user, _ = build_database_user(
            database_id=database.id,
            tenant_id=tenant_id,
            username=db_user_name,
            plain_password=plain_password,
            host="%",
            max_connections=20,
            grants=["ALL PRIVILEGES"],
        )
        await self._db.provision_user(database, user, plain_password)
        return database.id, user.id, database_name, db_user_name, plain_password

    def _setup_directories(self, site_path: Path) -> None:
        for sub in ("wordpress", "nginx", "backups"):
            (site_path / sub).mkdir(parents=True, exist_ok=True)
        os.chmod(site_path, 0o750)
        os.chmod(site_path / "wordpress", 0o750)
        os.chmod(site_path / "nginx", 0o750)

    def _write_configs(
        self,
        site_path: Path,
        site: WordPressSite,
        db_name: str,
        db_user: str,
        db_password: str,
        nginx_name: str,
        php_name: str,
    ) -> None:
        table_prefix = site.settings.get("table_prefix", "wp_")
        salts = site.settings.get("salts") or _generate_wp_salts()
        site.settings["salts"] = salts
        site.settings["table_prefix"] = table_prefix

        wp_config = _render_wp_config(
            db_name=db_name,
            db_user=db_user,
            db_password=db_password,
            db_host=f"{self._settings.mysql_host}:{self._settings.mysql_port}",
            table_prefix=table_prefix,
            salts=salts,
        )
        wp_config_path = site_path / "wordpress" / "wp-config.php"
        wp_config_path.write_text(wp_config, encoding="utf-8")
        os.chmod(wp_config_path, 0o640)

        nginx_conf_path = site_path / "nginx" / "default.conf"
        nginx_conf_path.write_text(_render_nginx_conf(), encoding="utf-8")

        router_name = f"wp-{str(site.id).split('-')[0]}"
        php_image = f"wordpress:php{site.php_version}-fpm"
        compose = _render_compose(
            nginx_name=nginx_name,
            php_name=php_name,
            php_image=php_image,
            php_version=site.php_version,
            domain=site.domain,
            router_name=router_name,
            ssl_enabled=site.ssl_enabled,
        )
        (site_path / "docker-compose.yml").write_text(compose, encoding="utf-8")

    async def _exec(self, *args: str, cwd: Path | None = None) -> str:
        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=str(cwd) if cwd else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=docker_subprocess_env(self._settings),
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode() or stdout.decode() or f"Command failed: {' '.join(args)}")
        return stdout.decode()

    async def _run_wp_cli(self, compose_path: Path, *args: str) -> str:
        return await self._exec(
            "docker", "compose", "-f", str(compose_path),
            "--profile", "cli", "run", "--rm", "wp-cli",
            *args,
            cwd=compose_path.parent,
        )

    async def deploy(
        self,
        site: WordPressSite,
        admin_password: str,
        db_name: str,
        db_user: str,
        db_password: str,
        nginx_name: str,
        php_name: str,
    ) -> None:
        site_path = Path(site.site_path)
        self._setup_directories(site_path)
        self._write_configs(site_path, site, db_name, db_user, db_password, nginx_name, php_name)

        compose_path = site_path / "docker-compose.yml"
        await self._exec("docker", "compose", "-f", str(compose_path), "up", "-d", cwd=site_path)

        await self._run_wp_cli(compose_path, "wp", "core", "download", "--force")
        await self._run_wp_cli(
            compose_path,
            "wp", "core", "install",
            f"--url={site.url}",
            f"--title={site.name}",
            f"--admin_user={site.admin_user}",
            f"--admin_password={admin_password}",
            f"--admin_email={site.admin_email}",
            "--skip-email",
        )

        self._apply_permissions(site_path)

    def _apply_permissions(self, site_path: Path) -> None:
        wp_dir = site_path / "wordpress"
        for root, dirs, files in os.walk(wp_dir):
            os.chmod(root, 0o755)
            for d in dirs:
                os.chmod(os.path.join(root, d), 0o755)
            for f in files:
                fpath = os.path.join(root, f)
                mode = 0o640 if f == "wp-config.php" else 0o644
                os.chmod(fpath, mode)

    async def restart(self, site: WordPressSite) -> None:
        compose_path = Path(site.site_path) / "docker-compose.yml"
        await self._exec("docker", "compose", "-f", str(compose_path), "restart")

    async def stop(self, site: WordPressSite) -> None:
        compose_path = Path(site.site_path) / "docker-compose.yml"
        if compose_path.exists():
            await self._exec("docker", "compose", "-f", str(compose_path), "stop")

    async def start(self, site: WordPressSite) -> None:
        compose_path = Path(site.site_path) / "docker-compose.yml"
        if compose_path.exists():
            await self._exec("docker", "compose", "-f", str(compose_path), "up", "-d")

    async def destroy(self, site: WordPressSite) -> None:
        compose_path = Path(site.site_path) / "docker-compose.yml"
        if compose_path.exists():
            try:
                await self._exec("docker", "compose", "-f", str(compose_path), "down", "-v", "--remove-orphans")
            except Exception:
                pass
        for name in (site.nginx_container_name, site.php_container_name):
            if name:
                try:
                    await self._exec("docker", "rm", "-f", validate_container_name(name))
                except Exception:
                    pass
        site_path = Path(site.site_path)
        if site_path.exists():
            shutil.rmtree(site_path, ignore_errors=True)

    async def change_php_version(self, site: WordPressSite, new_version: str) -> None:
        site.php_version = new_version
        db_password = self._crypto.decrypt(site.settings["db_password_enc"])
        nginx_name = site.nginx_container_name or ""
        php_name = site.php_container_name or ""
        self._write_configs(
            Path(site.site_path),
            site,
            site.settings["db_name"],
            site.settings["db_user"],
            db_password,
            nginx_name,
            php_name,
        )
        compose_path = Path(site.site_path) / "docker-compose.yml"
        await self._exec("docker", "compose", "-f", str(compose_path), "up", "-d", "--force-recreate", "php")

    async def set_maintenance(self, site: WordPressSite, enabled: bool) -> None:
        site_path = Path(site.site_path)
        maintenance_file = site_path / "wordpress" / ".maintenance"
        if enabled:
            maintenance_file.write_text("<?php $upgrading = time(); ?>", encoding="utf-8")
        elif maintenance_file.exists():
            maintenance_file.unlink()

    def measure_disk_mb(self, site: WordPressSite) -> int:
        wp_dir = Path(site.site_path) / "wordpress"
        if not wp_dir.exists():
            return 0
        total = sum(f.stat().st_size for f in wp_dir.rglob("*") if f.is_file())
        return max(1, total // (1024 * 1024))

    async def create_backup(self, site: WordPressSite, backup: WordPressBackup) -> None:
        site_path = Path(site.site_path)
        backup_path = self.get_backup_path(site.tenant_id, site.id, backup.id)
        temp_dir = site_path / "backups" / str(backup.id)
        temp_dir.mkdir(parents=True, exist_ok=True)

        if backup.includes_files:
            files_archive = temp_dir / "files.tar.gz"
            with tarfile.open(files_archive, "w:gz") as tar:
                tar.add(site_path / "wordpress", arcname="wordpress")

        if backup.includes_database and site.settings.get("db_name"):
            db_dump = temp_dir / "database.sql"
            proc = await asyncio.create_subprocess_exec(
                "mysqldump",
                "-h", self._settings.mysql_host,
                "-P", str(self._settings.mysql_port),
                "-u", site.settings["db_user"],
                f"-p{self._crypto.decrypt(site.settings['db_password_enc'])}",
                site.settings["db_name"],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(stderr.decode() or "mysqldump failed")
            db_dump.write_bytes(stdout)

        with tarfile.open(backup_path, "w:gz") as tar:
            tar.add(temp_dir, arcname=".")
        shutil.rmtree(temp_dir, ignore_errors=True)

        size_mb = max(1, backup_path.stat().st_size // (1024 * 1024))
        backup.mark_completed(str(backup_path), size_mb, compute_checksum(backup_path))

    async def restore_backup(self, site: WordPressSite, backup: WordPressBackup) -> None:
        if not backup.file_path or not Path(backup.file_path).exists():
            raise RuntimeError("Backup file not found")
        site_path = Path(site.site_path)
        temp_dir = site_path / "backups" / "restore"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True)

        with tarfile.open(backup.file_path, "r:gz") as tar:
            tar.extractall(temp_dir)

        files_src = temp_dir / "wordpress"
        if files_src.exists():
            dest = site_path / "wordpress"
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(files_src, dest)

        db_dump = temp_dir / "database.sql"
        if db_dump.exists() and site.settings.get("db_name"):
            proc = await asyncio.create_subprocess_exec(
                "mysql",
                "-h", self._settings.mysql_host,
                "-P", str(self._settings.mysql_port),
                "-u", site.settings["db_user"],
                f"-p{self._crypto.decrypt(site.settings['db_password_enc'])}",
                site.settings["db_name"],
                stdin=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate(db_dump.read_bytes())
            if proc.returncode != 0:
                raise RuntimeError(stderr.decode() or "mysql restore failed")

        shutil.rmtree(temp_dir, ignore_errors=True)
        await self.restart(site)

    async def clone_site_files(self, source: WordPressSite, target_path: Path) -> None:
        src = Path(source.site_path) / "wordpress"
        dst = target_path / "wordpress"
        if src.exists():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        self._apply_permissions(target_path)

    def encrypt_db_password(self, password: str) -> str:
        return self._crypto.encrypt(password)

    def decrypt_db_password(self, encrypted: str) -> str:
        return self._crypto.decrypt(encrypted)
