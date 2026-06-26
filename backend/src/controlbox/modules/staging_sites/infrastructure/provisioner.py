import asyncio
import hashlib
import os
import secrets
import shutil
import subprocess
from pathlib import Path
from uuid import UUID

from controlbox.config.settings import Settings
from controlbox.modules.databases.domain.entities import DatabaseEngineType, DatabaseStatus
from controlbox.modules.databases.infrastructure.engine_adapters import generate_password
from controlbox.modules.databases.infrastructure.provisioner import (
    DatabaseProvisioner,
    build_database_user,
    build_managed_database,
)
from controlbox.modules.staging_sites.domain.entities import (
    StagingSite,
    StagingSourceType,
    StagingStackType,
    SyncType,
)
from controlbox.modules.supabase.infrastructure.crypto import SecretEncryptor
from controlbox.shared.infrastructure.mysql_cli import mysql_connection_args
from controlbox.modules.websites.domain.entities import RUNTIME_PORTS
from controlbox.modules.platform.infrastructure.runtime_catalog import RUNTIME_IMAGE_MAP
from controlbox.modules.wordpress.infrastructure.provisioner import (
    WordPressProvisioner,
    _render_wp_config,
)
from controlbox.modules.joomla.infrastructure.provisioner import JoomlaProvisioner
from controlbox.shared.infrastructure.docker.env import docker_subprocess_env, validate_container_name


TEMPLATE_ROOT = Path(__file__).resolve().parents[6] / "infra" / "staging" / "templates"


class StagingProvisioner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._db = DatabaseProvisioner(settings)
        self._crypto = SecretEncryptor(settings)
        self._wp = WordPressProvisioner(settings)
        self._joomla = JoomlaProvisioner(settings)


    def get_staging_path(self, tenant_id: UUID, staging_id: UUID) -> Path:
        return Path(self._settings.sites_base_path) / str(tenant_id) / "staging" / str(staging_id)

    def _load_template(self, name: str) -> str:
        path = TEMPLATE_ROOT / name
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def _render(self, template: str, variables: dict[str, str]) -> str:
        result = template
        for key, value in variables.items():
            result = result.replace(f"{{{{{key}}}}}", value)
        return result

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

    async def provision_database(self, tenant_id: UUID, staging_id: UUID) -> tuple[UUID, UUID, str, str, str]:
        db_slug = f"stg_{staging_id.hex[:8]}"
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
            raise RuntimeError("Failed to provision staging database")

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

    async def clone_database_from_source(
        self,
        source_db_name: str,
        source_db_user: str,
        source_db_password: str,
        target_db_name: str,
        target_db_user: str,
        target_db_password: str,
    ) -> None:
        proc = await asyncio.create_subprocess_exec(
            "mysqldump",
            *mysql_connection_args(
                self._settings.mysql_host,
                self._settings.mysql_port,
                source_db_user,
                source_db_password,
            ),
            source_db_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode() or "mysqldump failed")

        import_proc = await asyncio.create_subprocess_exec(
            "mysql",
            *mysql_connection_args(
                self._settings.mysql_host,
                self._settings.mysql_port,
                target_db_user,
                target_db_password,
            ),
            target_db_name,
            stdin=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, import_stderr = await import_proc.communicate(stdout)
        if import_proc.returncode != 0:
            raise RuntimeError(import_stderr.decode() or "mysql import failed")

    async def clone_files_website(self, source_path: Path, target_path: Path) -> None:
        target_path.mkdir(parents=True, exist_ok=True)
        public_src = source_path / "public"
        if public_src.exists():
            shutil.copytree(public_src, target_path / "public", dirs_exist_ok=True)
        for name in ("package.json", "server.js", "main.py", "requirements.txt", "Dockerfile"):
            src_file = source_path / name
            if src_file.exists():
                shutil.copy2(src_file, target_path / name)
        logs_dir = target_path / "logs"
        logs_dir.mkdir(exist_ok=True)

    async def clone_files_wordpress(self, source_path: Path, target_path: Path) -> None:
        src = source_path / "wordpress"
        dst = target_path / "wordpress"
        if src.exists():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        (target_path / "nginx").mkdir(parents=True, exist_ok=True)

    def _build_htpasswd(self, username: str, password: str) -> str:
        result = subprocess.run(
            ["openssl", "passwd", "-apr1", password],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return f"{username}:{result.stdout.strip()}"
        digest = hashlib.sha1(password.encode()).hexdigest()
        return f"{username}:{{SHA}}{digest}"

    def _security_blocks(self, staging: StagingSite) -> tuple[str, str, str]:
        ip_block = ""
        auth_block = ""
        middleware_chain = []

        security = staging.settings.get("security", {})
        if staging.public_access_blocked:
            auth_block = """
    auth_basic "Staging Access Restricted";
    auth_basic_user_file /etc/nginx/.htpasswd;
"""
            middleware_chain.append(f"{staging.traefik_router}-block")

        if security.get("password_protection", {}).get("enabled"):
            auth_block = """
    auth_basic "Staging Protected";
    auth_basic_user_file /etc/nginx/.htpasswd;
"""
            middleware_chain.append(f"{staging.traefik_router}-auth")

        if security.get("ip_restriction", {}).get("enabled"):
            ips = security["ip_restriction"].get("allowed_ips", [])
            if ips:
                allow_lines = "\n".join(f"        allow {ip};" for ip in ips)
                ip_block = f"""
    {allow_lines}
        deny all;
"""
                middleware_chain.append(f"{staging.traefik_router}-ipwhitelist")

        if not middleware_chain:
            middleware_chain.append(f"{staging.traefik_router}-noop")

        return ip_block, auth_block, ",".join(middleware_chain)

    async def deploy_wordpress(self, staging: StagingSite, db_name: str, db_user: str, db_password: str) -> None:
        site_path = Path(staging.site_path)
        site_path.mkdir(parents=True, exist_ok=True)
        (site_path / "nginx").mkdir(exist_ok=True)

        salts = staging.settings.get("salts") or {f"KEY_{i}": secrets.token_urlsafe(32) for i in range(8)}
        staging.settings["salts"] = salts
        table_prefix = staging.settings.get("table_prefix", "wp_")

        wp_config = _render_wp_config(
            db_name=db_name,
            db_user=db_user,
            db_password=db_password,
            db_host=f"{self._settings.mysql_host}:{self._settings.mysql_port}",
            table_prefix=table_prefix,
            salts=salts,
        )
        wp_config_path = site_path / "wordpress" / "wp-config.php"
        wp_config_path.parent.mkdir(parents=True, exist_ok=True)
        wp_config_path.write_text(wp_config, encoding="utf-8")
        os.chmod(wp_config_path, 0o640)

        ip_block, auth_block, middleware_chain = self._security_blocks(staging)
        nginx_template = self._load_template("nginx.wordpress.conf")
        nginx_conf = self._render(nginx_template, {
            "IP_RESTRICTION": ip_block,
            "AUTH_BLOCK": auth_block,
        })
        (site_path / "nginx" / "default.conf").write_text(nginx_conf, encoding="utf-8")

        security = staging.settings.get("security", {})
        if auth_block:
            user = security.get("password_protection", {}).get("username", "staging")
            password = security.get("password_protection", {}).get("password", secrets.token_urlsafe(12))
            (site_path / "nginx" / ".htpasswd").write_text(
                self._build_htpasswd(user, password) + "\n",
                encoding="utf-8",
            )
        else:
            (site_path / "nginx" / ".htpasswd").write_text("blocked:blocked\n", encoding="utf-8")

        php_version = staging.runtime_version or "8.3"
        compose_template = self._load_template("docker-compose.wordpress.yml")
        compose = self._render(compose_template, {
            "NGINX_CONTAINER": staging.nginx_container_name or "",
            "PHP_CONTAINER": staging.php_container_name or "",
            "PHP_VERSION": php_version,
            "DOMAIN": staging.domain,
            "ROUTER_NAME": staging.traefik_router or "",
            "MIDDLEWARE_NAME": middleware_chain.split(",")[0] if middleware_chain else f"{staging.traefik_router}-noop",
            "STAGING_ID": str(staging.id),
            "TENANT_ID": str(staging.tenant_id),
        })
        (site_path / "docker-compose.yml").write_text(compose, encoding="utf-8")
        await self._exec("docker", "compose", "-f", str(site_path / "docker-compose.yml"), "up", "-d", cwd=site_path)

    async def deploy_joomla_staging(self, staging: StagingSite, db_name: str, db_user: str, db_password: str) -> None:
        site_path = Path(staging.site_path)
        site_path.mkdir(parents=True, exist_ok=True)
        (site_path / "nginx").mkdir(exist_ok=True)
        (site_path / "logs").mkdir(exist_ok=True)

        ip_block, auth_block, middleware_chain = self._security_blocks(staging)
        nginx_template = self._load_template("nginx.joomla.conf")
        if not nginx_template:
            nginx_template = """server {
    listen 80;
    server_name _;
    root /var/www/html;
    index index.php index.html;
    client_max_body_size 128M;

    {{IP_RESTRICTION}}

    {{AUTH_BLOCK}}

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
}
"""
        nginx_conf = self._render(nginx_template, {
            "IP_RESTRICTION": ip_block,
            "AUTH_BLOCK": auth_block,
        })
        (site_path / "nginx" / "default.conf").write_text(nginx_conf, encoding="utf-8")

        security = staging.settings.get("security", {})
        if auth_block:
            user = security.get("password_protection", {}).get("username", "staging")
            password = security.get("password_protection", {}).get("password", secrets.token_urlsafe(12))
            (site_path / "nginx" / ".htpasswd").write_text(
                self._build_htpasswd(user, password) + "\n",
                encoding="utf-8",
            )
        else:
            (site_path / "nginx" / ".htpasswd").write_text("blocked:blocked\n", encoding="utf-8")

        php_version = staging.runtime_version or "8.3"
        compose_template = self._load_template("docker-compose.joomla.yml")
        if not compose_template:
            compose_template = """services:
  nginx:
    image: nginx:1.27-alpine
    container_name: {{NGINX_CONTAINER}}
    restart: unless-stopped
    volumes:
      - ./joomla:/var/www/html:ro
      - ./nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
      - ./nginx/.htpasswd:/etc/nginx/.htpasswd:ro
    depends_on:
      - php
    networks:
      - controlbox
      - stg_internal
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.{{ROUTER_NAME}}.rule=Host(`{{DOMAIN}}`)"
      - "traefik.http.routers.{{ROUTER_NAME}}.entrypoints=websecure"
      - "traefik.http.services.{{ROUTER_NAME}}.loadbalancer.server.port=80"
      - "traefik.http.routers.{{ROUTER_NAME}}.tls=true"
      - "traefik.http.routers.{{ROUTER_NAME}}.tls.certresolver=letsencrypt"
      - "traefik.http.routers.{{ROUTER_NAME}}.middlewares={{MIDDLEWARE_NAME}}"
      - "controlbox.staging=true"
      - "controlbox.staging.id={{STAGING_ID}}"
      - "controlbox.tenant.id={{TENANT_ID}}"
      - "controlbox.monitoring.scrape=true"
      - "controlbox.monitoring.port=80"
      - "controlbox.logs.enabled=true"

  php:
    image: wordpress:php{{PHP_VERSION}}-fpm
    container_name: {{PHP_CONTAINER}}
    restart: unless-stopped
    volumes:
      - ./joomla:/var/www/html
    networks:
      - controlbox
      - stg_internal
    user: "33:33"

networks:
  controlbox:
    external: true
  stg_internal:
    driver: bridge
"""
        compose = self._render(compose_template, {
            "NGINX_CONTAINER": staging.nginx_container_name or "",
            "PHP_CONTAINER": staging.php_container_name or "",
            "PHP_VERSION": php_version,
            "DOMAIN": staging.domain,
            "ROUTER_NAME": staging.traefik_router or "",
            "MIDDLEWARE_NAME": middleware_chain.split(",")[0] if middleware_chain else f"{staging.traefik_router}-noop",
            "STAGING_ID": str(staging.id),
            "TENANT_ID": str(staging.tenant_id),
        })
        (site_path / "docker-compose.yml").write_text(compose, encoding="utf-8")
        await self._exec("docker", "compose", "-f", str(site_path / "docker-compose.yml"), "up", "-d", cwd=site_path)

    async def deploy_website(self, staging: StagingSite) -> None:

        site_path = Path(staging.site_path)
        site_path.mkdir(parents=True, exist_ok=True)
        (site_path / "public").mkdir(exist_ok=True)
        (site_path / "logs").mkdir(exist_ok=True)

        stack = staging.stack_type.value
        image_key = (stack, staging.runtime_version)
        image = RUNTIME_IMAGE_MAP.get(image_key) or RUNTIME_IMAGE_MAP.get((stack, "")) or "nginx:1.27-alpine"
        port = RUNTIME_PORTS.get(stack, 80)
        container_port = 8000 if stack == "python" else port

        build_section = ""
        command_section = ""
        volume_section = "- ./public:/usr/share/nginx/html\n      - ./logs:/var/log/app"

        if stack == "python":
            build_section = "build: ."
            volume_section = "- ./logs:/var/log/app"
        elif stack == "nodejs":
            command_section = 'command: sh -c "npm install && npm start"'
            volume_section = "- .:/app\n      - ./logs:/var/log/app"
        elif stack == "php":
            volume_section = "- ./public:/var/www/html\n      - ./logs:/var/log/app"
            image = RUNTIME_IMAGE_MAP.get(("php", staging.runtime_version), "php:8.3-apache")

        _, _, middleware_chain = self._security_blocks(staging)
        compose_template = self._load_template("docker-compose.website.yml")
        compose = self._render(compose_template, {
            "IMAGE": image,
            "CONTAINER_NAME": staging.container_name or "",
            "BUILD_SECTION": build_section,
            "COMMAND_SECTION": command_section,
            "VOLUME_SECTION": volume_section,
            "DOMAIN": staging.domain,
            "ROUTER_NAME": staging.traefik_router or "",
            "PORT": str(container_port),
            "MIDDLEWARE_NAME": middleware_chain.split(",")[0],
            "STAGING_ID": str(staging.id),
            "TENANT_ID": str(staging.tenant_id),
        })
        (site_path / "docker-compose.yml").write_text(compose, encoding="utf-8")

        if staging.database_config:
            env_lines = [f"{k}={v}" for k, v in staging.database_config.items()]
            (site_path / ".env").write_text("\n".join(env_lines), encoding="utf-8")

        await self._exec("docker", "compose", "-f", str(site_path / "docker-compose.yml"), "up", "-d", cwd=site_path)

    async def provision(self, staging: StagingSite, uow) -> None:
        target_path = self.get_staging_path(staging.tenant_id, staging.id)
        staging.site_path = str(target_path)

        has_database = staging.stack_type in (StagingStackType.WORDPRESS, StagingStackType.JOOMLA, StagingStackType.PHP)
        db_name = db_user = db_password = ""
        if has_database:
            db_id, user_id, db_name, db_user, db_password = await self.provision_database(
                staging.tenant_id, staging.id
            )
            staging.managed_database_id = db_id
            staging.database_user_id = user_id
            staging.settings.update({
                "db_name": db_name,
                "db_user": db_user,
                "db_password_enc": self._crypto.encrypt(db_password),
            })

        if staging.source_type == StagingSourceType.WORDPRESS:
            source = await uow.wordpress_sites.get_by_id_and_tenant(staging.source_id, staging.tenant_id)
            if source is None:
                raise RuntimeError("Source WordPress site not found")
            source_path = Path(source.site_path)
            await self.clone_files_wordpress(source_path, target_path)
            if source.settings.get("db_name"):
                src_password = self._wp.decrypt_db_password(source.settings["db_password_enc"])
                await self.clone_database_from_source(
                    source.settings["db_name"],
                    source.settings["db_user"],
                    src_password,
                    db_name,
                    db_user,
                    db_password,
                )
            staging.runtime_version = source.php_version
            await self.deploy_wordpress(staging, db_name, db_user, db_password)
        elif staging.source_type == StagingSourceType.JOOMLA:
            source = await uow.joomla_sites.get_by_id_and_tenant(staging.source_id, staging.tenant_id)
            if source is None:
                raise RuntimeError("Source Joomla site not found")
            source_path = Path(source.site_path)
            await self._joomla.clone_site_files(source, target_path)
            if source.settings.get("db_name"):
                src_password = self._joomla.decrypt_db_password(source.settings["db_password_enc"])
                await self.clone_database_from_source(
                    source.settings["db_name"],
                    source.settings["db_user"],
                    src_password,
                    db_name,
                    db_user,
                    db_password,
                )
            staging.runtime_version = source.php_version
            staging.settings["cms_version"] = source.joomla_version
            await self.deploy_joomla_staging(staging, db_name, db_user, db_password)

        else:
            source = await uow.websites.get_by_id_and_tenant(staging.source_id, staging.tenant_id)
            if source is None:
                raise RuntimeError("Source website not found")
            source_path = Path(self._settings.sites_base_path) / str(staging.tenant_id) / str(source.id)
            await self.clone_files_website(source_path, target_path)
            if source.database_config and has_database:
                src_cfg = source.database_config
                if src_cfg.get("database") and src_cfg.get("username") and src_cfg.get("password"):
                    await self.clone_database_from_source(
                        src_cfg["database"],
                        src_cfg["username"],
                        src_cfg["password"],
                        db_name,
                        db_user,
                        db_password,
                    )
                    staging.database_config = {
                        "DATABASE_URL": (
                            f"mysql://{db_user}:{db_password}@"
                            f"{self._settings.mysql_host}:{self._settings.mysql_port}/{db_name}"
                        ),
                    }
            await self.deploy_website(staging)

        staging.activate_ssl()
        staging.update_metrics(0.0, 0, self.measure_disk_mb(target_path))

    async def sync(
        self,
        staging: StagingSite,
        uow,
        sync_type: SyncType,
        to_production: bool = False,
    ) -> None:
        target_path = Path(staging.site_path)
        if staging.source_type == StagingSourceType.WORDPRESS:
            source = await uow.wordpress_sites.get_by_id_and_tenant(staging.source_id, staging.tenant_id)
            if source is None:
                raise RuntimeError("Source not found")
            source_path = Path(source.site_path)
            if sync_type in (SyncType.FILES, SyncType.FULL):
                if to_production:
                    if (target_path / "wordpress").exists():
                        prod_wp = source_path / "wordpress"
                        if prod_wp.exists():
                            shutil.rmtree(prod_wp)
                        shutil.copytree(target_path / "wordpress", prod_wp)
                else:
                    await self.clone_files_wordpress(source_path, target_path)
            if sync_type in (SyncType.DATABASE, SyncType.FULL) and staging.settings.get("db_name"):
                stg_password = self._crypto.decrypt(staging.settings["db_password_enc"])
                if to_production and source.settings.get("db_name"):
                    src_password = self._wp.decrypt_db_password(source.settings["db_password_enc"])
                    await self.clone_database_from_source(
                        staging.settings["db_name"],
                        staging.settings["db_user"],
                        stg_password,
                        source.settings["db_name"],
                        source.settings["db_user"],
                        src_password,
                    )
                elif source.settings.get("db_name"):
                    src_password = self._wp.decrypt_db_password(source.settings["db_password_enc"])
                    await self.clone_database_from_source(
                        source.settings["db_name"],
                        source.settings["db_user"],
                        src_password,
                        staging.settings["db_name"],
                        staging.settings["db_user"],
                        stg_password,
        elif staging.source_type == StagingSourceType.JOOMLA:
            source = await uow.joomla_sites.get_by_id_and_tenant(staging.source_id, staging.tenant_id)
            if source is None:
                raise RuntimeError("Source not found")
            source_path = Path(source.site_path)
            if sync_type in (SyncType.FILES, SyncType.FULL):
                if to_production:
                    if (target_path / "joomla").exists():
                        prod_jm = source_path / "joomla"
                        if prod_jm.exists():
                            shutil.rmtree(prod_jm)
                        shutil.copytree(target_path / "joomla", prod_jm)
                else:
                    await self._joomla.clone_site_files(source, target_path)
            if sync_type in (SyncType.DATABASE, SyncType.FULL) and staging.settings.get("db_name"):
                stg_password = self._crypto.decrypt(staging.settings["db_password_enc"])
                if to_production and source.settings.get("db_name"):
                    src_password = self._joomla.decrypt_db_password(source.settings["db_password_enc"])
                    await self.clone_database_from_source(
                        staging.settings["db_name"],
                        staging.settings["db_user"],
                        stg_password,
                        source.settings["db_name"],
                        source.settings["db_user"],
                        src_password,
                    )
                elif source.settings.get("db_name"):
                    src_password = self._joomla.decrypt_db_password(source.settings["db_password_enc"])
                    await self.clone_database_from_source(
                        source.settings["db_name"],
                        source.settings["db_user"],
                        src_password,
                        staging.settings["db_name"],
                        staging.settings["db_user"],
                        stg_password,
                    )
        else:
            source = await uow.websites.get_by_id_and_tenant(staging.source_id, staging.tenant_id)
            if source is None:
                raise RuntimeError("Source not found")
            source_path = Path(self._settings.sites_base_path) / str(staging.tenant_id) / str(source.id)
            if sync_type in (SyncType.FILES, SyncType.FULL):
                if to_production:
                    if (target_path / "public").exists():
                        prod_public = source_path / "public"
                        if prod_public.exists():
                            shutil.rmtree(prod_public)
                        shutil.copytree(target_path / "public", prod_public)
                else:
                    await self.clone_files_website(source_path, target_path)

        await self.restart(staging)
        staging.update_metrics(staging.cpu_usage_percent, staging.memory_used_mb, self.measure_disk_mb(target_path))

    async def restart(self, staging: StagingSite) -> None:
        compose_path = Path(staging.site_path) / "docker-compose.yml"
        if compose_path.exists():
            await self._exec("docker", "compose", "-f", str(compose_path), "restart", cwd=Path(staging.site_path))

    async def destroy(self, staging: StagingSite) -> None:
        compose_path = Path(staging.site_path) / "docker-compose.yml"
        if compose_path.exists():
            try:
                await self._exec(
                    "docker", "compose", "-f", str(compose_path), "down", "-v", "--remove-orphans",
                    cwd=Path(staging.site_path),
                )
            except Exception:
                pass
        for name in (staging.container_name, staging.nginx_container_name, staging.php_container_name):
            if name:
                try:
                    await self._exec("docker", "rm", "-f", validate_container_name(name))
                except Exception:
                    pass
        site_path = Path(staging.site_path)
        if site_path.exists():
            shutil.rmtree(site_path, ignore_errors=True)

    def measure_disk_mb(self, site_path: Path) -> int:
        if not site_path.exists():
            return 0
        total = sum(f.stat().st_size for f in site_path.rglob("*") if f.is_file())
        return max(1, total // (1024 * 1024))

    async def collect_metrics(self, staging: StagingSite) -> tuple[float, int, int]:
        disk = self.measure_disk_mb(Path(staging.site_path))
        cpu = 0.0
        memory = 0
        container = staging.nginx_container_name or staging.container_name
        if container:
            try:
                output = await self._exec(
                    "docker", "stats", "--no-stream", "--format",
                    "{{.CPUPerc}} {{.MemUsage}}", validate_container_name(container),
                )
                parts = output.strip().split()
                if parts:
                    cpu = float(parts[0].replace("%", ""))
                if len(parts) > 1:
                    mem_part = parts[1].split("/")[0].strip()
                    if mem_part.endswith("MiB"):
                        memory = int(float(mem_part.replace("MiB", "")))
                    elif mem_part.endswith("GiB"):
                        memory = int(float(mem_part.replace("GiB", "")) * 1024)
            except Exception:
                pass
        return cpu, memory, disk
