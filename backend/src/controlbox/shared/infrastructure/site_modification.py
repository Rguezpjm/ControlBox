"""Site modification (aaPanel-style) — read/write VHOST, domains, and site settings."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from controlbox.config.settings import Settings
from controlbox.modules.websites.domain.entities import Website, WebsiteRuntime
from controlbox.modules.websites.infrastructure.provisioner import DockerProvisioner, RUNTIME_PORTS
from controlbox.modules.wordpress.domain.entities import WordPressSite
from controlbox.shared.infrastructure.docker.env import docker_subprocess_env


def default_site_settings(primary_domain: str, document_root: str = "") -> dict[str, Any]:
    return {
        "domains": [{"domain": primary_domain, "port": 443, "primary": True}],
        "document_root": document_root,
        "index_files": ["index.php", "index.html", "index.htm"],
        "url_rewrite": "",
        "limit_access_enabled": False,
        "limit_access_user": "",
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
    document_root: str
    settings: dict[str, Any]
    vhost_config: str
    nginx_config: str | None
    access_log: str
    error_log: str


class SiteModificationService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._docker = DockerProvisioner(settings)

    def _website_path(self, website: Website) -> Path:
        return self._docker.get_site_path(website.tenant_id, website.id)

    def _wordpress_path(self, site: WordPressSite) -> Path:
        return Path(site.site_path) if site.site_path else Path("")

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

    async def get_website(self, website: Website) -> SiteModificationView:
        site_path = self._website_path(website)
        settings = merge_settings(website.settings, website.domain, website.document_root)
        compose = self._read_file(site_path / "docker-compose.yml", "# docker-compose.yml not found\n")
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
            document_root=website.document_root or str(site_path / "public"),
            settings=settings,
            vhost_config=compose,
            nginx_config=None,
            access_log=self._tail_log(site_path / "logs" / "access.log"),
            error_log=self._tail_log(site_path / "logs" / "error.log"),
        )

    async def get_wordpress(self, site: WordPressSite) -> SiteModificationView:
        site_path = self._wordpress_path(site)
        settings = merge_settings(site.settings, site.domain, str(site_path / "wordpress"))
        compose = self._read_file(site_path / "docker-compose.yml", "")
        nginx = self._read_file(site_path / "nginx" / "default.conf", "")
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
            document_root=str(site_path / "wordpress"),
            settings=settings,
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
        vhost_config: str | None = None,
        ssl_enabled: bool | None = None,
        runtime_version: str | None = None,
    ) -> SiteModificationView:
        site_path = self._website_path(website)
        settings = merge_settings(website.settings, website.domain, website.document_root)

        if settings_patch:
            settings.update(settings_patch)
            website.settings = settings

        if ssl_enabled is not None:
            website.ssl_enabled = ssl_enabled

        if runtime_version and website.runtime == WebsiteRuntime.PHP:
            website.runtime_version = runtime_version

        compose_path = site_path / "docker-compose.yml"

        if vhost_config is not None:
            compose_path.write_text(vhost_config, encoding="utf-8")
        elif settings_patch and settings.get("domains"):
            if compose_path.is_file():
                host_rule = self._traefik_host_rule(settings["domains"])
                updated = self._patch_compose_hosts(compose_path.read_text(encoding="utf-8"), host_rule)
                compose_path.write_text(updated, encoding="utf-8")

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
        vhost_config: str | None = None,
        nginx_config: str | None = None,
        ssl_enabled: bool | None = None,
        php_version: str | None = None,
    ) -> SiteModificationView:
        site_path = self._wordpress_path(site)
        settings = merge_settings(site.settings, site.domain, str(site_path / "wordpress"))

        if settings_patch:
            settings.update(settings_patch)
            site.settings = settings
            if "maintenance_mode" in settings_patch:
                site.maintenance_mode = bool(settings_patch["maintenance_mode"])

        if ssl_enabled is not None:
            site.ssl_enabled = ssl_enabled

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

        if nginx_config is not None:
            nginx_path.write_text(nginx_config, encoding="utf-8")
        elif settings.get("url_rewrite"):
            custom = site_path / "nginx" / "rewrite.conf"
            custom.write_text(settings["url_rewrite"], encoding="utf-8")

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
