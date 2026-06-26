import asyncio
import hashlib
import os
import secrets
import shutil
import tarfile
from pathlib import Path
from uuid import UUID

from controlbox.config.settings import Settings
from controlbox.modules.databases.infrastructure.engine_adapters import compute_checksum
from controlbox.modules.supabase.infrastructure.crypto import SecretEncryptor
from controlbox.modules.wordpress.domain.entities import WordPressBackup, WordPressSite
from controlbox.shared.infrastructure.traefik_labels import compose_label_lines, traefik_router_labels
from controlbox.shared.infrastructure.docker.env import docker_subprocess_env, validate_container_name
from controlbox.shared.infrastructure.mysql_cli import mysql_connection_args
from controlbox.shared.infrastructure.site_directory_config import (
    render_wordpress_nginx,
    write_directory_security_files,
)


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

    access_log /var/log/nginx/access.log combined;
    error_log /var/log/nginx/error.log warn;

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
    site_uid: int,
    site_gid: int,
    php_image_override: str | None = None,
) -> str:
    label_map = traefik_router_labels(
        router_name,
        domain,
        80,
        ssl_enabled=ssl_enabled,
        extra={
            "controlbox.wordpress": "true",
            "controlbox.logs.enabled": "true",
        },
    )
    tls_labels = "\n" + "\n".join(compose_label_lines(label_map)) + "\n"
    php_source = f"image: {php_image_override or php_image}"
    return f"""services:
  nginx:
    image: nginx:1.27-alpine
    container_name: {nginx_name}
    restart: unless-stopped
    volumes:
      - ./wordpress:/var/www/html:ro
      - ./nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
      - ./nginx/.htpasswd:/etc/nginx/.htpasswd:ro
      - ./logs:/var/log/nginx
    depends_on:
      - php
    networks:
      - controlbox
      - wp_internal
    labels:
      - "traefik.enable=true"
{tls_labels}
  php:
    {php_source}
    container_name: {php_name}
    restart: unless-stopped
    volumes:
      - ./wordpress:/var/www/html
      - ./nginx/php-security.ini:/usr/local/etc/php/conf.d/zzz-controlbox.ini:ro
    networks:
      - controlbox
      - wp_internal
    user: "{site_uid}:{site_gid}"

  wp-cli:
    image: wordpress:cli-php{php_version}
    profiles: [cli]
    volumes:
      - ./wordpress:/var/www/html
    networks:
      - controlbox
      - wp_internal
    user: "{site_uid}:{site_gid}"
    working_dir: /var/www/html
    environment:
      HOME: /tmp
      WP_CLI_CACHE_DIR: /tmp/.wp-cli/cache
      WP_CLI_PHP_ARGS: "-d memory_limit=512M"

networks:
  controlbox:
    external: true
  wp_internal:
    driver: bridge
"""


class WordPressProvisioner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._crypto = SecretEncryptor(settings)

    def get_site_path(self, tenant_id: UUID, site_id: UUID) -> Path:
        return Path(self._settings.sites_base_path) / str(tenant_id) / "wordpress" / str(site_id)

    def get_backup_path(self, tenant_id: UUID, site_id: UUID, backup_id: UUID) -> Path:
        path = Path(self._settings.backups_base_path) / str(tenant_id) / "wordpress" / str(site_id)
        path.mkdir(parents=True, exist_ok=True)
        return path / f"{backup_id}.tar.gz"

    def _setup_directories(self, site_path: Path) -> None:
        for sub in ("wordpress", "nginx", "backups", "logs"):
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
        site_directory = site_path / "wordpress"
        settings = site.settings or {}
        settings.setdefault("document_root", str(site_directory))
        settings.setdefault("running_directory", "/")
        settings.setdefault("open_basedir_enabled", True)
        settings.setdefault("logs_enabled", True)
        write_directory_security_files(
            site_path,
            settings,
            site_directory=site_directory,
            mount_path=Path("/var/www/html"),
        )
        nginx_conf_path.write_text(render_wordpress_nginx(settings, site_directory), encoding="utf-8")

        router_name = f"wp-{str(site.id).split('-')[0]}"
        php_image = f"wordpress:php{site.php_version}-fpm"
        try:
            wp_stat = (site_path / "wordpress").stat()
            site_uid, site_gid = wp_stat.st_uid, wp_stat.st_gid
        except OSError:
            site_uid, site_gid = os.getuid(), os.getgid()
        compose = _render_compose(
            nginx_name=nginx_name,
            php_name=php_name,
            php_image=php_image,
            php_version=site.php_version,
            domain=site.domain,
            router_name=router_name,
            ssl_enabled=site.ssl_enabled,
            site_uid=site_uid,
            site_gid=site_gid,
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
        # The official `wordpress:cli` image runs the WP-CLI phar through its shebang,
        # so it ignores WP_CLI_PHP_ARGS and keeps the image's 128M CLI memory_limit,
        # which OOMs while extracting the WordPress download. Invoke the phar through
        # php explicitly so we can raise memory_limit / execution time reliably.
        run_args: tuple[str, ...] = args
        if args and args[0] == "wp":
            run_args = (
                "php",
                "-d", "memory_limit=512M",
                "-d", "max_execution_time=600",
                "/usr/local/bin/wp",
                *args[1:],
            )
        return await self._exec(
            "docker", "compose", "-f", str(compose_path),
            "--profile", "cli", "run", "--rm", "wp-cli",
            *run_args,
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

        # Esperar a que el contenedor de PHP termine de copiar los archivos de WordPress al volumen.
        # El entrypoint oficial de wordpress copia los archivos al iniciar si no existen en el volumen.
        wp_settings = site_path / "wordpress" / "wp-settings.php"
        for _ in range(60):  # Esperar hasta 30 segundos
            if wp_settings.exists() and wp_settings.stat().st_size > 0:
                await asyncio.sleep(1)  # Margen de seguridad para asegurar la escritura completa
                break
            await asyncio.sleep(0.5)

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

    async def change_admin_password(self, site: WordPressSite, new_password: str) -> None:
        compose_path = Path(site.site_path) / "docker-compose.yml"
        if not compose_path.is_file():
            raise RuntimeError("WordPress no está instalado en este sitio")
        await self._run_wp_cli(
            compose_path,
            "wp",
            "user",
            "update",
            site.admin_user,
            f"--user_pass={new_password}",
        )

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
                *mysql_connection_args(
                    self._settings.mysql_host,
                    self._settings.mysql_port,
                    site.settings["db_user"],
                    self._crypto.decrypt(site.settings["db_password_enc"]),
                ),
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
                *mysql_connection_args(
                    self._settings.mysql_host,
                    self._settings.mysql_port,
                    site.settings["db_user"],
                    self._crypto.decrypt(site.settings["db_password_enc"]),
                ),
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
