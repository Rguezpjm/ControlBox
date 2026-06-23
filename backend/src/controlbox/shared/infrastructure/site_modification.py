"""Site modification — read/write VHOST, domains, and site settings."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from controlbox.config.settings import Settings
from controlbox.modules.websites.domain.entities import Website, WebsiteRuntime, SslStatus
from controlbox.modules.websites.infrastructure.provisioner import DockerProvisioner, RUNTIME_PORTS
from controlbox.modules.wordpress.domain.entities import WordPressSite, WordPressSslStatus
from controlbox.modules.wordpress.infrastructure.provisioner import (
    WordPressProvisioner,
    _render_compose as render_wordpress_compose,
)
from controlbox.shared.infrastructure.custom_ssl import CustomSslInfo, CustomSslManager
from controlbox.shared.infrastructure.docker.env import docker_subprocess_env
from controlbox.shared.infrastructure.site_directory_config import (
    list_running_directory_options,
    patch_wordpress_compose_bindings,
    render_wordpress_nginx,
    validate_site_directory,
    write_directory_security_files,
    write_php_htaccess_security,
)


def default_site_settings(primary_domain: str, document_root: str = "") -> dict[str, Any]:
    return {
        "domains": [{"domain": primary_domain, "port": 443, "primary": True}],
        "document_root": document_root,
        "index_files": ["index.php", "index.html", "index.htm"],
        "url_rewrite": "",
        "limit_access_enabled": False,
        "limit_access_user": "",
        "limit_access_password": "",
        "running_directory": "/",
        "open_basedir_enabled": True,
        "logs_enabled": True,
        "subdirectory_bindings": [],
        "redirects": [],
        "reverse_proxy_enabled": False,
        "reverse_proxy_target": "",
        "hotlink_protection": False,
        "maintenance_mode": False,
    }


def merge_settings(current: dict[str, Any], primary_domain: str, document_root: str = "") -> dict[str, Any]:
    base = default_site_settings(primary_domain, document_root)
    merged = {**base, **(current or {})}
    if not merged.get("domains"):
        merged["domains"] = base["domains"]
    return merged


@dataclass
class SiteModificationView:
    site_type: str
    site_id: UUID
    name: str
    primary_domain: str
    status: str
    created_at: datetime
    runtime: str | None
    runtime_version: str | None
    php_version: str | None
    ssl_enabled: bool
    ssl_status: str
    ssl_config: CustomSslInfo | None
    document_root: str
    running_directory: str
    running_directory_options: list[str]
    open_basedir_enabled: bool
    logs_enabled: bool
    site_files_path: str
    site_path: str
    subdirectory_bindings: list[dict[str, Any]]
    settings: dict[str, Any]
    vhost_config: str
    nginx_config: str | None
    access_log: str
    error_log: str


class SiteModificationService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._docker = DockerProvisioner(settings)
        self._ssl = CustomSslManager(settings)

    def _router_prefix(self, site_type: str) -> str:
        return "wp-" if site_type == "wordpress" else "site-"

    def _apply_ssl_settings(
        self,
        site_type: str,
        site_id: UUID,
        primary_domain: str,
        settings: dict[str, Any],
        *,
        ssl_enabled: bool | None = None,
        ssl_provider: str | None = None,
        ssl_certificate_pem: str | None = None,
        ssl_private_key_pem: str | None = None,
        ssl_force_https: bool | None = None,
    ) -> dict[str, Any]:
        ssl_settings = self._ssl.get_ssl_settings(settings)

        if ssl_force_https is not None:
            ssl_settings["force_https"] = ssl_force_https

        if ssl_provider is not None:
            if ssl_provider == "letsencrypt" and ssl_settings.get("provider") == "custom":
                self._ssl.remove_custom_certificate(site_type, site_id)
            ssl_settings["provider"] = ssl_provider

        if ssl_provider == "custom" or (
            ssl_settings.get("provider") == "custom"
            and ssl_certificate_pem
            and ssl_private_key_pem
        ):
            if not ssl_certificate_pem or not ssl_private_key_pem:
                raise ValueError("Custom SSL requires both certificate and private key")
            self._ssl.save_custom_certificate(
                site_type,
                site_id,
                primary_domain,
                ssl_certificate_pem,
                ssl_private_key_pem,
            )
            ssl_settings["provider"] = "custom"

        if ssl_enabled is False or ssl_provider == "none":
            self._ssl.remove_custom_certificate(site_type, site_id)
            ssl_settings["provider"] = "none"

        settings["ssl"] = ssl_settings
        return settings

    def _patch_compose_for_ssl(
        self,
        compose_path: Path,
        site_type: str,
        settings: dict[str, Any],
        ssl_enabled: bool,
    ) -> None:
        if not compose_path.is_file():
            return
        ssl_settings = self._ssl.get_ssl_settings(settings)
        provider = str(ssl_settings.get("provider") or "letsencrypt")
        if not ssl_enabled or provider == "none":
            provider = "none"
        elif provider != "custom":
            provider = "letsencrypt"
        compose_text = compose_path.read_text(encoding="utf-8")
        updated = self._ssl.patch_compose_ssl(
            compose_text,
            self._router_prefix(site_type),
            ssl_enabled=ssl_enabled and provider != "none",
            provider=provider,
        )
        compose_path.write_text(updated, encoding="utf-8")

    def _website_path(self, website: Website) -> Path:
        return self._docker.get_site_path(website.tenant_id, website.id)

    def _wordpress_path(self, site: WordPressSite) -> Path:
        if site.site_path:
            stored = Path(site.site_path)
            if stored.is_dir():
                return stored
        if site.tenant_id:
            fallback = WordPressProvisioner(self._settings).get_site_path(site.tenant_id, site.id)
            if fallback.is_dir():
                return fallback
            return fallback
        return Path(site.site_path) if site.site_path else Path("")

    def _ensure_wordpress_nginx(self, site_path: Path, settings: dict[str, Any], document_root: str) -> str:
        nginx_path = site_path / "nginx" / "default.conf"
        if nginx_path.is_file():
            content = nginx_path.read_text(encoding="utf-8", errors="replace")
            if content.strip():
                return content
        site_directory = Path(document_root) if document_root else site_path / "wordpress"
        if not site_directory.is_dir():
            site_directory = site_path / "wordpress"
        rendered = render_wordpress_nginx(settings, site_directory)
        if site_path.is_dir():
            try:
                nginx_path.parent.mkdir(parents=True, exist_ok=True)
                nginx_path.write_text(rendered, encoding="utf-8")
            except OSError:
                pass
        return rendered

    def _ensure_website_compose(self, website: Website, site_path: Path) -> str:
        compose_path = site_path / "docker-compose.yml"
        if compose_path.is_file():
            content = compose_path.read_text(encoding="utf-8", errors="replace")
            if content.strip():
                return content
        if not site_path.is_dir():
            return "# docker-compose.yml not found\n"
        try:
            if not website.container_name:
                website.container_name = f"cb-site-{str(website.id).split('-')[0]}"
            self._docker._write_compose(site_path, website)
            if compose_path.is_file():
                return compose_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
        return "# docker-compose.yml not found\n"

    def _ensure_wordpress_compose(self, site: WordPressSite, site_path: Path) -> str:
        compose_path = site_path / "docker-compose.yml"
        if compose_path.is_file():
            content = compose_path.read_text(encoding="utf-8", errors="replace")
            if content.strip():
                return content
        short = str(site.id).split("-")[0]
        nginx_name = site.nginx_container_name or f"cb-wp-nginx-{short}"
        php_name = site.php_container_name or f"cb-wp-php-{short}"
        php_image = f"wordpress:php{site.php_version}-fpm"
        rendered = render_wordpress_compose(
            nginx_name=nginx_name,
            php_name=php_name,
            php_image=php_image,
            php_version=site.php_version,
            domain=site.domain,
            router_name=f"wp-{short}",
            ssl_enabled=site.ssl_enabled,
        )
        if site_path.is_dir():
            try:
                compose_path.write_text(rendered, encoding="utf-8")
            except OSError:
                pass
        return rendered

    def _read_file(self, path: Path, default: str = "") -> str:
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")
        return default

    def _tail_log(self, path: Path, lines: int = 80) -> str:
        if not path.is_file():
            return ""
        try:
            content = path.read_text(encoding="utf-8", errors="replace").splitlines()
            return "\n".join(content[-lines:])
        except OSError:
            return ""

    def _default_wordpress_rewrite(self) -> str:
        return """<IfModule mod_authz_core.c>
    <FilesMatch "(?i)\\.(env|sql|log|bak|old|ini|sh|yml|yaml|pem|key|crt)$">
        Require all denied
    </FilesMatch>
</IfModule>

<IfModule mod_headers.c>
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-Frame-Options "SAMEORIGIN"
</IfModule>

<IfModule mod_rewrite.c>
RewriteEngine On
RewriteBase /
RewriteRule ^index\\.php$ - [L]
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule . /index.php [L]
</IfModule>

# BEGIN WordPress
<IfModule mod_rewrite.c>
RewriteEngine On
RewriteRule .* - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]
RewriteBase /
RewriteRule ^index\\.php$ - [L]
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule . /index.php [L]
</IfModule>
# END WordPress
"""

    def _traefik_host_rule(self, domains: list[dict[str, Any]]) -> str:
        hosts = [d["domain"] for d in domains if d.get("domain")]
        if not hosts:
            return "Host(`localhost`)"
        if len(hosts) == 1:
            return f"Host(`{hosts[0]}`)"
        return " || ".join(f"Host(`{h}`)" for h in hosts)

    async def _exec_compose(self, compose_path: Path, *args: str) -> None:
        proc = await asyncio.create_subprocess_exec(
            "docker",
            "compose",
            "-f",
            str(compose_path),
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=docker_subprocess_env(self._settings),
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode() or stdout.decode() or "docker compose failed")

    def _site_files_path(self, tenant_id: UUID, site_path: Path) -> str:
        tenant_root = Path(self._settings.sites_base_path) / str(tenant_id)
        try:
            rel = site_path.resolve().relative_to(tenant_root.resolve())
            return "" if rel.as_posix() == "." else rel.as_posix()
        except ValueError:
            return ""

    def _directory_fields(
        self,
        site_path: Path,
        document_root: str,
        settings: dict[str, Any],
        *,
        logs_enabled: bool,
        site_files_path: str = "",
    ) -> dict[str, Any]:
        site_directory = Path(document_root)
        running_directory = str(settings.get("running_directory") or "/")
        return {
            "running_directory": running_directory,
            "running_directory_options": list_running_directory_options(site_directory),
            "open_basedir_enabled": settings.get("open_basedir_enabled", True) is not False,
            "logs_enabled": logs_enabled if settings.get("logs_enabled") is None else bool(settings.get("logs_enabled")),
            "site_files_path": site_files_path,
            "site_path": str(site_path.resolve()),
            "subdirectory_bindings": list(settings.get("subdirectory_bindings") or []),
        }

    def _apply_wordpress_directory(self, site: WordPressSite, settings: dict[str, Any]) -> None:
        site_path = self._wordpress_path(site)
        if not site_path.is_dir():
            return
        site_directory = Path(settings.get("document_root") or str(site_path / "wordpress"))
        try:
            site_directory = validate_site_directory(site_path, str(site_directory))
        except ValueError:
            site_directory = site_path / "wordpress"
        settings["document_root"] = str(site_directory)

        write_directory_security_files(
            site_path,
            settings,
            site_directory=site_directory,
            mount_path=Path("/var/www/html"),
        )
        nginx_path = site_path / "nginx" / "default.conf"
        nginx_path.parent.mkdir(parents=True, exist_ok=True)
        nginx_path.write_text(render_wordpress_nginx(settings, site_directory), encoding="utf-8")

        compose_path = site_path / "docker-compose.yml"
        if compose_path.is_file():
            router_prefix = f"wp-{str(site.id).split('-')[0]}"
            updated = patch_wordpress_compose_bindings(
                compose_path.read_text(encoding="utf-8"),
                settings.get("subdirectory_bindings") or [],
                router_prefix,
            )
            compose_path.write_text(updated, encoding="utf-8")

    def _apply_website_directory(self, website: Website, settings: dict[str, Any]) -> None:
        site_path = self._website_path(website)
        if not site_path.is_dir():
            return
        document_root = website.document_root or str(site_path / "public")
        try:
            document_root_path = validate_site_directory(site_path, document_root)
        except ValueError:
            document_root_path = site_path / "public"
        website.document_root = str(document_root_path)
        settings["document_root"] = website.document_root

        if website.runtime == WebsiteRuntime.PHP:
            container_root = "/var/www/html"
            running = str(settings.get("running_directory") or "/").strip("/")
            if running:
                container_root = f"/var/www/html/{running}"
            write_php_htaccess_security(
                document_root_path,
                settings.get("open_basedir_enabled", True) is not False,
                container_root,
            )

    def _sync_logs_enabled(self, settings: dict[str, Any], website: Website | None = None) -> bool:
        if website is not None:
            if settings.get("logs_enabled") is not None:
                website.logs_enabled = bool(settings["logs_enabled"])
            elif website.logs_enabled is not None:
                settings["logs_enabled"] = website.logs_enabled
        return bool(settings.get("logs_enabled", True))

    def _patch_compose_hosts(self, compose_text: str, host_rule: str, router_prefix: str = "site") -> str:
        lines = compose_text.splitlines()
        out: list[str] = []
        for line in lines:
            if "traefik.http.routers." in line and ".rule=" in line:
                key = line.split('"')[0].strip().removeprefix("- ").strip()
                if router_prefix in key or "wp-" in key or "site-" in key:
                    indent = line[: line.index("-")] if line.strip().startswith("-") else "      "
                    out.append(f'{indent}- "{key}={host_rule}"')
                    continue
            out.append(line)
        return "\n".join(out) + ("\n" if compose_text.endswith("\n") else "")

    def _resolve_document_root(self, site_path: Path, document_root: str) -> Path:
        raw = Path(str(document_root).replace("\\", "/"))
        if not raw.is_absolute():
            candidate = (site_path / raw).resolve()
        else:
            candidate = raw.resolve()
        return validate_site_directory(site_path, str(candidate))

    def _public_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        public = dict(settings)
        public.pop("limit_access_password", None)
        return public

    async def get_website(self, website: Website) -> SiteModificationView:
        site_path = self._website_path(website)
        settings = merge_settings(website.settings, website.domain, website.document_root)
        self._sync_logs_enabled(settings, website)
        document_root = website.document_root or str(site_path / "public")
        directory = self._directory_fields(
            site_path,
            document_root,
            settings,
            logs_enabled=website.logs_enabled,
            site_files_path=self._site_files_path(website.tenant_id, site_path),
        )
        compose = self._ensure_website_compose(website, site_path)
        ssl_info = self._ssl.build_info("website", website.id, settings, website.domain)
        return SiteModificationView(
            site_type="website",
            site_id=website.id,
            name=website.name,
            primary_domain=website.domain,
            status=website.status.value,
            created_at=website.created_at,
            runtime=website.runtime.value,
            runtime_version=website.runtime_version,
            php_version=website.runtime_version if website.runtime == WebsiteRuntime.PHP else None,
            ssl_enabled=website.ssl_enabled,
            ssl_status=website.ssl_status.value,
            ssl_config=ssl_info,
            document_root=document_root,
            running_directory=directory["running_directory"],
            running_directory_options=directory["running_directory_options"],
            open_basedir_enabled=directory["open_basedir_enabled"],
            logs_enabled=directory["logs_enabled"],
            site_files_path=directory["site_files_path"],
            site_path=directory["site_path"],
            subdirectory_bindings=directory["subdirectory_bindings"],
            settings=self._public_settings(settings),
            vhost_config=compose,
            nginx_config=None,
            access_log=self._tail_log(site_path / "logs" / "access.log"),
            error_log=self._tail_log(site_path / "logs" / "error.log"),
        )

    async def get_wordpress(self, site: WordPressSite) -> SiteModificationView:
        site_path = self._wordpress_path(site)
        document_root = str(site_path / "wordpress")
        settings = merge_settings(site.settings, site.domain, document_root)
        if settings.get("document_root"):
            document_root = str(settings["document_root"])
        if not settings.get("url_rewrite"):
            htaccess = self._read_file(Path(document_root) / ".htaccess", "")
            settings["url_rewrite"] = htaccess if htaccess.strip() else self._default_wordpress_rewrite()
        self._sync_logs_enabled(settings)
        directory = self._directory_fields(
            site_path,
            document_root,
            settings,
            logs_enabled=bool(settings.get("logs_enabled", True)),
            site_files_path=self._site_files_path(site.tenant_id, site_path),
        )
        compose = self._ensure_wordpress_compose(site, site_path)
        nginx = self._ensure_wordpress_nginx(site_path, settings, document_root)
        ssl_info = self._ssl.build_info("wordpress", site.id, settings, site.domain)
        return SiteModificationView(
            site_type="wordpress",
            site_id=site.id,
            name=site.name,
            primary_domain=site.domain,
            status=site.status.value,
            created_at=site.created_at,
            runtime="wordpress",
            runtime_version=None,
            php_version=site.php_version,
            ssl_enabled=site.ssl_enabled,
            ssl_status=site.ssl_status.value,
            ssl_config=ssl_info,
            document_root=document_root,
            running_directory=directory["running_directory"],
            running_directory_options=directory["running_directory_options"],
            open_basedir_enabled=directory["open_basedir_enabled"],
            logs_enabled=directory["logs_enabled"],
            site_files_path=directory["site_files_path"],
            site_path=directory["site_path"],
            subdirectory_bindings=directory["subdirectory_bindings"],
            settings=self._public_settings(settings),
            vhost_config=compose,
            nginx_config=nginx,
            access_log=self._tail_log(site_path / "logs" / "access.log"),
            error_log=self._tail_log(site_path / "logs" / "error.log"),
        )

    async def update_website(
        self,
        website: Website,
        *,
        settings_patch: dict[str, Any] | None = None,
        document_root: str | None = None,
        logs_enabled: bool | None = None,
        vhost_config: str | None = None,
        ssl_enabled: bool | None = None,
        runtime_version: str | None = None,
        ssl_provider: str | None = None,
        ssl_certificate_pem: str | None = None,
        ssl_private_key_pem: str | None = None,
        ssl_force_https: bool | None = None,
    ) -> SiteModificationView:
        site_path = self._website_path(website)
        settings = merge_settings(website.settings, website.domain, website.document_root)

        if document_root is not None:
            website.document_root = self._resolve_document_root(site_path, document_root).as_posix()
            settings["document_root"] = website.document_root

        if logs_enabled is not None:
            website.logs_enabled = logs_enabled
            settings["logs_enabled"] = logs_enabled

        if settings_patch:
            settings.update(settings_patch)
            website.settings = settings

        try:
            settings = self._apply_ssl_settings(
                "website",
                website.id,
                website.domain,
                settings,
                ssl_enabled=ssl_enabled,
                ssl_provider=ssl_provider,
                ssl_certificate_pem=ssl_certificate_pem,
                ssl_private_key_pem=ssl_private_key_pem,
                ssl_force_https=ssl_force_https,
            )
            website.settings = settings
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc

        if ssl_enabled is not None:
            website.ssl_enabled = ssl_enabled
            if ssl_enabled:
                website.ssl_status = SslStatus.ACTIVE
            else:
                website.ssl_status = SslStatus.PENDING

        ssl_cfg = self._ssl.get_ssl_settings(settings)
        if ssl_cfg.get("provider") == "custom" and ssl_enabled is not False:
            website.ssl_enabled = True
            website.ssl_status = SslStatus.ACTIVE

        if runtime_version:
            website.runtime_version = runtime_version

        compose_path = site_path / "docker-compose.yml"

        if vhost_config is not None:
            compose_path.write_text(vhost_config, encoding="utf-8")
        elif settings_patch and settings.get("domains"):
            if compose_path.is_file():
                host_rule = self._traefik_host_rule(settings["domains"])
                updated = self._patch_compose_hosts(compose_path.read_text(encoding="utf-8"), host_rule)
                compose_path.write_text(updated, encoding="utf-8")
        elif runtime_version and website.runtime != WebsiteRuntime.PYTHON:
            self._docker._write_compose(site_path, website)

        self._patch_compose_for_ssl(compose_path, "website", settings, website.ssl_enabled)

        directory_touched = document_root is not None or logs_enabled is not None or (
            settings_patch
            and any(
                key in settings_patch
                for key in (
                    "running_directory",
                    "open_basedir_enabled",
                    "logs_enabled",
                    "limit_access_enabled",
                    "limit_access_user",
                    "limit_access_password",
                    "subdirectory_bindings",
                    "document_root",
                )
            )
        )
        if directory_touched:
            try:
                self._apply_website_directory(website, settings)
                website.settings = settings
            except ValueError as exc:
                raise RuntimeError(str(exc)) from exc

        if settings.get("url_rewrite"):
            rewrite_path = site_path / "public" / ".htaccess"
            rewrite_path.write_text(settings["url_rewrite"], encoding="utf-8")

        if compose_path.is_file():
            await self._exec_compose(compose_path, "up", "-d", "--force-recreate")

        return await self.get_website(website)

    async def update_wordpress(
        self,
        site: WordPressSite,
        *,
        settings_patch: dict[str, Any] | None = None,
        document_root: str | None = None,
        logs_enabled: bool | None = None,
        vhost_config: str | None = None,
        nginx_config: str | None = None,
        ssl_enabled: bool | None = None,
        php_version: str | None = None,
        ssl_provider: str | None = None,
        ssl_certificate_pem: str | None = None,
        ssl_private_key_pem: str | None = None,
        ssl_force_https: bool | None = None,
    ) -> SiteModificationView:
        site_path = self._wordpress_path(site)
        settings = merge_settings(site.settings, site.domain, str(site_path / "wordpress"))

        if document_root is not None:
            validated = self._resolve_document_root(site_path, document_root)
            settings["document_root"] = str(validated)

        if logs_enabled is not None:
            settings["logs_enabled"] = logs_enabled

        if settings_patch:
            settings.update(settings_patch)
            site.settings = settings
            if "maintenance_mode" in settings_patch:
                site.maintenance_mode = bool(settings_patch["maintenance_mode"])

        try:
            settings = self._apply_ssl_settings(
                "wordpress",
                site.id,
                site.domain,
                settings,
                ssl_enabled=ssl_enabled,
                ssl_provider=ssl_provider,
                ssl_certificate_pem=ssl_certificate_pem,
                ssl_private_key_pem=ssl_private_key_pem,
                ssl_force_https=ssl_force_https,
            )
            site.settings = settings
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc

        if ssl_enabled is not None:
            site.ssl_enabled = ssl_enabled
            if ssl_enabled:
                site.ssl_status = WordPressSslStatus.ACTIVE
            else:
                site.ssl_status = WordPressSslStatus.PENDING

        ssl_cfg = self._ssl.get_ssl_settings(settings)
        if ssl_cfg.get("provider") == "custom" and ssl_enabled is not False:
            site.ssl_enabled = True
            site.ssl_status = WordPressSslStatus.ACTIVE

        if php_version:
            site.php_version = php_version

        compose_path = site_path / "docker-compose.yml"
        nginx_path = site_path / "nginx" / "default.conf"

        if vhost_config is not None:
            compose_path.write_text(vhost_config, encoding="utf-8")
        elif settings_patch and settings.get("domains") and compose_path.is_file():
            host_rule = self._traefik_host_rule(settings["domains"])
            updated = self._patch_compose_hosts(compose_path.read_text(encoding="utf-8"), host_rule, "wp-")
            compose_path.write_text(updated, encoding="utf-8")

        self._patch_compose_for_ssl(compose_path, "wordpress", settings, site.ssl_enabled)

        if nginx_config is not None:
            nginx_path.write_text(nginx_config, encoding="utf-8")
        elif settings.get("url_rewrite"):
            try:
                wp_root = Path(settings.get("document_root") or str(site_path / "wordpress"))
                wp_root.mkdir(parents=True, exist_ok=True)
                (wp_root / ".htaccess").write_text(settings["url_rewrite"], encoding="utf-8")
            except OSError:
                pass
            custom = site_path / "nginx" / "rewrite.conf"
            custom.write_text(settings["url_rewrite"], encoding="utf-8")
        else:
            directory_touched = document_root is not None or logs_enabled is not None or (
                settings_patch
                and any(
                    key in settings_patch
                    for key in (
                        "running_directory",
                        "open_basedir_enabled",
                        "logs_enabled",
                        "limit_access_enabled",
                        "limit_access_user",
                        "limit_access_password",
                        "subdirectory_bindings",
                        "document_root",
                    )
                )
            )
            if directory_touched:
                try:
                    self._apply_wordpress_directory(site, settings)
                    site.settings = settings
                except ValueError as exc:
                    raise RuntimeError(str(exc)) from exc

        if compose_path.is_file():
            await self._exec_compose(compose_path, "up", "-d", "--force-recreate")

        return await self.get_wordpress(site)

    def add_domain(self, settings: dict[str, Any], domain: str, port: int = 443) -> dict[str, Any]:
        domains = list(settings.get("domains") or [])
        domain = domain.strip().lower()
        if any(d.get("domain") == domain for d in domains):
            return settings
        domains.append({"domain": domain, "port": port, "primary": False})
        settings["domains"] = domains
        return settings

    def remove_domain(self, settings: dict[str, Any], domain: str) -> dict[str, Any]:
        domain = domain.strip().lower()
        domains = [d for d in settings.get("domains", []) if d.get("domain") != domain or d.get("primary")]
        settings["domains"] = domains
        return settings
