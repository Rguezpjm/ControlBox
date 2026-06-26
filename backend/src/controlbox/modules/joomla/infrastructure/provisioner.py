import asyncio
import hashlib
import os
import re
import secrets
import shutil
import tarfile
import urllib.request
import zipfile
from pathlib import Path
from uuid import UUID

from controlbox.config.settings import Settings
from controlbox.modules.databases.infrastructure.engine_adapters import compute_checksum
from controlbox.modules.supabase.infrastructure.crypto import SecretEncryptor
from controlbox.modules.joomla.domain.entities import JoomlaBackup, JoomlaSite
from controlbox.shared.infrastructure.traefik_labels import compose_label_lines, traefik_router_labels
from controlbox.shared.infrastructure.docker.env import docker_subprocess_env, validate_container_name
from controlbox.shared.infrastructure.mysql_cli import mysql_connection_args
from controlbox.shared.infrastructure.site_directory_config import (
    render_joomla_nginx,
    write_directory_security_files,
)


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

    location /api/ {
        try_files $uri $uri/ /api/index.php?$args;
    }

    location ~ \\.php$ {
        fastcgi_pass php:9000;
        fastcgi_index index.php;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        include fastcgi_params;
        fastcgi_read_timeout 300;
    }

    location ~* /(images|cache|media|logs|tmp)/.*\\.(php|pl|py|jsp|asp|sh|cgi)$ {
        deny all;
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
            "controlbox.joomla": "true",
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
      - ./joomla:/var/www/html:ro
      - ./nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
      - ./nginx/.htpasswd:/etc/nginx/.htpasswd:ro
      - ./logs:/var/log/nginx
    depends_on:
      - php
    networks:
      - controlbox
      - jm_internal
    labels:
      - "traefik.enable=true"
{tls_labels}
  php:
    {php_source}
    container_name: {php_name}
    restart: unless-stopped
    volumes:
      - ./joomla:/var/www/html
      - ./nginx/php-security.ini:/usr/local/etc/php/conf.d/zzz-controlbox.ini:ro
    networks:
      - controlbox
      - jm_internal
    user: "{site_uid}:{site_gid}"

networks:
  controlbox:
    external: true
  jm_internal:
    driver: bridge
"""


class JoomlaProvisioner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._crypto = SecretEncryptor(settings)

    def get_site_path(self, tenant_id: UUID, site_id: UUID) -> Path:
        return Path(self._settings.sites_base_path) / str(tenant_id) / "joomla" / str(site_id)

    def get_backup_path(self, tenant_id: UUID, site_id: UUID, backup_id: UUID) -> Path:
        path = Path(self._settings.backups_base_path) / str(tenant_id) / "joomla" / str(site_id)
        path.mkdir(parents=True, exist_ok=True)
        return path / f"{backup_id}.tar.gz"

    def _setup_directories(self, site_path: Path) -> None:
        for sub in ("joomla", "nginx", "backups", "logs"):
            (site_path / sub).mkdir(parents=True, exist_ok=True)
        os.chmod(site_path, 0o750)
        os.chmod(site_path / "joomla", 0o750)
        os.chmod(site_path / "nginx", 0o750)

    def _write_configs(
        self,
        site_path: Path,
        site: JoomlaSite,
        nginx_name: str,
        php_name: str,
    ) -> None:
        nginx_conf_path = site_path / "nginx" / "default.conf"
        site_directory = site_path / "joomla"
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
        nginx_conf_path.write_text(render_joomla_nginx(settings, site_directory), encoding="utf-8")

        router_name = f"jm-{str(site.id).split('-')[0]}"
        # We use wordpress image because it has php-fpm pre-configured with gd, mysqli, zip, etc.
        php_image = f"wordpress:php{site.php_version}-fpm"
        try:
            jm_stat = (site_path / "joomla").stat()
            site_uid, site_gid = jm_stat.st_uid, jm_stat.st_gid
        except OSError:
            try:
                site_uid, site_gid = os.getuid(), os.getgid()
            except AttributeError:
                site_uid, site_gid = 1000, 1000
        compose = _render_compose(
            nginx_name=nginx_name,
            php_name=php_name,
            php_image=php_image,
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

    async def _run_joomla_cli(self, compose_path: Path, *args: str) -> str:
        return await self._exec(
            "docker", "compose", "-f", str(compose_path),
            "run", "--rm", "php",
            *args,
            cwd=compose_path.parent,
        )

    def _ensure_joomla_zip(self) -> Path:
        download_dir = Path(self._settings.sites_base_path).parent / "downloads"
        download_dir.mkdir(parents=True, exist_ok=True)
        zip_path = download_dir / "joomla-5.1.1.zip"
        if not zip_path.exists():
            url = "https://github.com/joomla/joomla-cms/releases/download/5.1.1/Joomla_5.1.1-Stable-Full_Package.zip"
            urllib.request.urlretrieve(url, str(zip_path))
        return zip_path

    def _extract_joomla(self, zip_path: Path, dest_dir: Path) -> None:
        dest_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(dest_dir)

    async def deploy(
        self,
        site: JoomlaSite,
        admin_password: str,
        db_name: str,
        db_user: str,
        db_password: str,
        nginx_name: str,
        php_name: str,
    ) -> None:
        site_path = Path(site.site_path)
        self._setup_directories(site_path)
        self._write_configs(site_path, site, nginx_name, php_name)

        # Download and extract Joomla zip
        zip_path = self._ensure_joomla_zip()
        self._extract_joomla(zip_path, site_path / "joomla")

        compose_path = site_path / "docker-compose.yml"
        await self._exec("docker", "compose", "-f", str(compose_path), "up", "-d", cwd=site_path)

        # Joomla installation CLI
        await self._run_joomla_cli(
            compose_path,
            "php", "installation/joomla.php", "install",
            f"--site-name={site.name}",
            f"--admin-user={site.admin_user}",
            f"--admin-username={site.admin_user}",
            f"--admin-password={admin_password}",
            f"--admin-email={site.admin_email}",
            "--db-type=mysqli",
            f"--db-host={self._settings.mysql_host}",
            f"--db-user={db_user}",
            f"--db-pass={db_password}",
            f"--db-name={db_name}",
        )

        # Joomla requires you to delete the installation directory
        shutil.rmtree(site_path / "joomla" / "installation", ignore_errors=True)

        self._apply_permissions(site_path)

    async def change_admin_password(self, site: JoomlaSite, new_password: str) -> None:
        compose_path = Path(site.site_path) / "docker-compose.yml"
        if not compose_path.is_file():
            raise RuntimeError("Joomla no está instalado en este sitio")
        # In Joomla, we can set the password via the CLI console if the console command exists.
        # Alternatively, Joomla doesn't have user password updates via simple CLI arguments out of the box in installation CLI.
        # We can update the hash directly in the database!
        # Let's generate a Joomla-compatible bcrypt hash or standard php password_hash.
        # Let's execute SQL via php inside the container, or directly using mysql.
        # Joomla uses password_hash() (bcrypt) which is standard PHP.
        # Let's run a php command in the container that generates the hash and executes SQL to update the user!
        # The table prefix is available in settings or configuration.php.
        # Let's find table prefix from settings or read configuration.php:
        prefix = site.settings.get("db_prefix", "joom_")
        php_code = f"""
<?php
define('_JEXEC', 1);
define('JPATH_BASE', '/var/www/html');
require_once '/var/www/html/includes/defines.php';
require_once '/var/www/html/includes/framework.php';

$hash = password_hash('{new_password}', PASSWORD_BCRYPT);
$db = JFactory::getDbo();
$query = $db->getQuery(true);
$fields = array($db->quoteName('password') . ' = ' . $db->quote($hash));
$conditions = array($db->quoteName('username') . ' = ' . $db->quote('{site.admin_user}'));
$query->update($db->quoteName('#__users'))->set($fields)->where($conditions);
$db->setQuery($query);
$db->execute();
echo "UPDATED";
"""
        temp_php = Path(site.site_path) / "joomla" / "cb_pwd_update.php"
        temp_php.write_text(php_code, encoding="utf-8")
        try:
            await self._run_joomla_cli(compose_path, "php", "cb_pwd_update.php")
        finally:
            if temp_php.exists():
                temp_php.unlink()

    def _apply_permissions(self, site_path: Path) -> None:
        jm_dir = site_path / "joomla"
        for root, dirs, files in os.walk(jm_dir):
            try:
                os.chmod(root, 0o755)
            except OSError:
                pass
            for d in dirs:
                try:
                    os.chmod(os.path.join(root, d), 0o755)
                except OSError:
                    pass
            for f in files:
                fpath = os.path.join(root, f)
                mode = 0o640 if f == "configuration.php" else 0o644
                try:
                    os.chmod(fpath, mode)
                except OSError:
                    pass

    async def restart(self, site: JoomlaSite) -> None:
        compose_path = Path(site.site_path) / "docker-compose.yml"
        await self._exec("docker", "compose", "-f", str(compose_path), "restart")

    async def stop(self, site: JoomlaSite) -> None:
        compose_path = Path(site.site_path) / "docker-compose.yml"
        if compose_path.exists():
            await self._exec("docker", "compose", "-f", str(compose_path), "stop")

    async def start(self, site: JoomlaSite) -> None:
        compose_path = Path(site.site_path) / "docker-compose.yml"
        if compose_path.exists():
            await self._exec("docker", "compose", "-f", str(compose_path), "up", "-d")

    async def destroy(self, site: JoomlaSite) -> None:
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

    async def change_php_version(self, site: JoomlaSite, new_version: str) -> None:
        site.php_version = new_version
        self._write_configs(
            Path(site.site_path),
            site,
            site.nginx_container_name or "",
            site.php_container_name or "",
        )
        compose_path = Path(site.site_path) / "docker-compose.yml"
        await self._exec("docker", "compose", "-f", str(compose_path), "up", "-d", "--force-recreate", "php")

    async def set_maintenance(self, site: JoomlaSite, enabled: bool) -> None:
        config_path = Path(site.site_path) / "joomla" / "configuration.php"
        if not config_path.is_file():
            return
        text = config_path.read_text(encoding="utf-8", errors="replace")
        val = "1" if enabled else "0"
        pattern = r"public\s+\$offline\s*=\s*['\"]?[01]['\"]?\s*;"
        replacement = f"public $offline = '{val}';"
        if re.search(pattern, text):
            new_text = re.sub(pattern, replacement, text)
        else:
            new_text = text.replace("class JConfig {", f"class JConfig {{\n\tpublic $offline = '{val}';")
        config_path.write_text(new_text, encoding="utf-8")

    def measure_disk_mb(self, site: JoomlaSite) -> int:
        jm_dir = Path(site.site_path) / "joomla"
        if not jm_dir.exists():
            return 0
        total = sum(f.stat().st_size for f in jm_dir.rglob("*") if f.is_file())
        return max(1, total // (1024 * 1024))

    async def create_backup(self, site: JoomlaSite, backup: JoomlaBackup) -> None:
        site_path = Path(site.site_path)
        backup_path = self.get_backup_path(site.tenant_id, site.id, backup.id)
        temp_dir = site_path / "backups" / str(backup.id)
        temp_dir.mkdir(parents=True, exist_ok=True)

        if backup.includes_files:
            files_archive = temp_dir / "files.tar.gz"
            with tarfile.open(files_archive, "w:gz") as tar:
                tar.add(site_path / "joomla", arcname="joomla")

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

    async def restore_backup(self, site: JoomlaSite, backup: JoomlaBackup) -> None:
        if not backup.file_path or not Path(backup.file_path).exists():
            raise RuntimeError("Backup file not found")
        site_path = Path(site.site_path)
        temp_dir = site_path / "backups" / "restore"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True)

        with tarfile.open(backup.file_path, "r:gz") as tar:
            tar.extractall(temp_dir)

        files_src = temp_dir / "joomla"
        if files_src.exists():
            dest = site_path / "joomla"
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

    async def clone_site_files(self, source: JoomlaSite, target_path: Path) -> None:
        src = Path(source.site_path) / "joomla"
        dst = target_path / "joomla"
        if src.exists():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        self._apply_permissions(target_path)

    def encrypt_db_password(self, password: str) -> str:
        return self._crypto.encrypt(password)

    def decrypt_db_password(self, encrypted: str) -> str:
        return self._crypto.decrypt(encrypted)
