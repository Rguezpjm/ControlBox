import asyncio
import json
import secrets
import textwrap
from pathlib import Path
from uuid import UUID

from controlbox.config.settings import Settings
from controlbox.modules.websites.domain.entities import (
    DatabaseEngine,
    RUNTIME_PORTS,
    Website,
    WebsiteRuntime,
)
from controlbox.shared.infrastructure.docker.env import docker_subprocess_env, validate_container_name


RUNTIME_IMAGES: dict[tuple[str, str], str] = {
    ("html", ""): "nginx:1.27-alpine",
    ("php", "8.2"): "php:8.2-apache",
    ("php", "8.3"): "php:8.3-apache",
    ("nodejs", "22"): "node:22-alpine",
    ("python", "3.13"): "python:3.13-slim",
    ("flutter", "3.44.2"): "nginx:1.27-alpine",
}

class DockerProvisioner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get_site_path(self, tenant_id: UUID, website_id: UUID) -> Path:
        return Path(self._settings.sites_base_path) / str(tenant_id) / str(website_id)

    async def provision(self, website: Website) -> tuple[str, str]:
        site_path = self.get_site_path(website.tenant_id, website.id)
        site_path.mkdir(parents=True, exist_ok=True)
        (site_path / "public").mkdir(exist_ok=True)
        (site_path / "logs").mkdir(exist_ok=True)

        self._write_default_content(site_path, website)
        compose_path = self._write_compose(site_path, website)
        env_path = site_path / ".env"
        if website.database_config:
            env_path.write_text(self._format_env(website.database_config), encoding="utf-8")

        container_name = website.container_name or f"cb-site-{website.id.hex[:12]}"
        container_id = await self._run_compose(compose_path, container_name)
        return container_id, container_name

    async def stop(self, website: Website) -> None:
        if not website.container_name:
            return
        site_path = self.get_site_path(website.tenant_id, website.id)
        compose_path = site_path / "docker-compose.yml"
        if compose_path.exists():
            await self._exec("docker", "compose", "-f", str(compose_path), "stop")

    async def start(self, website: Website) -> None:
        site_path = self.get_site_path(website.tenant_id, website.id)
        compose_path = site_path / "docker-compose.yml"
        if compose_path.exists():
            await self._exec("docker", "compose", "-f", str(compose_path), "up", "-d")

    async def destroy(self, website: Website) -> None:
        site_path = self.get_site_path(website.tenant_id, website.id)
        compose_path = site_path / "docker-compose.yml"
        if compose_path.exists():
            await self._exec("docker", "compose", "-f", str(compose_path), "down", "-v", "--remove-orphans")
        if website.container_name:
            await self._exec("docker", "rm", "-f", validate_container_name(website.container_name))

    def _write_default_content(self, site_path: Path, website: Website) -> None:
        public = site_path / "public"
        runtime = website.runtime.value

        if runtime == "html":
            (public / "index.html").write_text(
                f"<!DOCTYPE html><html><head><title>{website.name}</title></head>"
                f"<body><h1>{website.name}</h1><p>ControlBox HTML Site</p></body></html>",
                encoding="utf-8",
            )
        elif runtime == "php":
            (public / "index.php").write_text(
                f"<?php echo '<h1>{website.name}</h1><p>PHP {website.runtime_version}</p>'; ?>",
                encoding="utf-8",
            )
        elif runtime == "nodejs":
            (site_path / "package.json").write_text(
                json.dumps({
                    "name": website.name.lower().replace(" ", "-"),
                    "version": "1.0.0",
                    "scripts": {"start": "node server.js"},
                    "dependencies": {"express": "^4.21.0"},
                }, indent=2),
                encoding="utf-8",
            )
            (site_path / "server.js").write_text(
                textwrap.dedent(f"""
                    const express = require('express');
                    const app = express();
                    const port = {RUNTIME_PORTS['nodejs']};
                    app.get('/', (req, res) => res.send('<h1>{website.name}</h1><p>Node.js {website.runtime_version}</p>'));
                    app.listen(port, '0.0.0.0', () => console.log(`Listening on ${{port}}`));
                """).strip(),
                encoding="utf-8",
            )
        elif runtime == "python":
            (site_path / "requirements.txt").write_text("fastapi==0.115.6\nuvicorn==0.32.1\n", encoding="utf-8")
            (site_path / "main.py").write_text(
                textwrap.dedent(f"""
                    from fastapi import FastAPI
                    from fastapi.responses import HTMLResponse
                    app = FastAPI()
                    @app.get("/")
                    def root():
                        return HTMLResponse("<h1>{website.name}</h1><p>Python {website.runtime_version}</p>")
                """).strip(),
                encoding="utf-8",
            )
            (site_path / "Dockerfile").write_text(
                textwrap.dedent("""
                    FROM python:3.13-slim
                    WORKDIR /app
                    COPY requirements.txt .
                    RUN pip install --no-cache-dir -r requirements.txt
                    COPY main.py .
                    CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
                """).strip(),
                encoding="utf-8",
            )
        elif runtime == "flutter":
            (public / "index.html").write_text(
                f"<!DOCTYPE html><html><head><title>{website.name}</title></head>"
                f"<body><h1>{website.name}</h1><p>Flutter Web {website.runtime_version}</p></body></html>",
                encoding="utf-8",
            )

    def _write_compose(self, site_path: Path, website: Website) -> Path:
        image_key = (website.runtime.value, website.runtime_version)
        image = RUNTIME_IMAGES.get(image_key) or RUNTIME_IMAGES.get((website.runtime.value, ""))
        port = RUNTIME_PORTS.get(website.runtime.value, 80)
        container_port = 8000 if website.runtime == WebsiteRuntime.PYTHON else port

        labels = self._build_traefik_labels(website, container_port)
        labels.update({
            "controlbox.monitoring.scrape": "true",
            "controlbox.monitoring.port": str(container_port),
            "controlbox.logs.enabled": "true",
            "controlbox.website.id": str(website.id),
            "controlbox.tenant.id": str(website.tenant_id),
        })
        label_lines = "\n".join(f'      - "{k}={v}"' for k, v in labels.items())

        if website.runtime == WebsiteRuntime.PYTHON:
            service_yaml = f"""  web:
    build: .
    container_name: {website.container_name}
    restart: unless-stopped
    environment:
      - DATABASE_URL=${{DATABASE_URL:-}}
    volumes:
      - ./logs:/var/log/app
    networks:
      - controlbox
      - site_network
    labels:
{label_lines}
"""
        elif website.runtime == WebsiteRuntime.NODEJS:
            service_yaml = f"""  web:
    image: {image}
    container_name: {website.container_name}
    restart: unless-stopped
    working_dir: /app
    command: sh -c "npm install && npm start"
    environment:
      - DATABASE_URL=${{DATABASE_URL:-}}
      - NODE_ENV=production
    volumes:
      - .:/app
      - ./logs:/var/log/app
    networks:
      - controlbox
      - site_network
    labels:
{label_lines}
"""
        else:
            volume_mount = "./public:/var/www/html" if website.runtime == WebsiteRuntime.PHP else "./public:/usr/share/nginx/html"
            service_yaml = f"""  web:
    image: {image}
    container_name: {website.container_name}
    restart: unless-stopped
    environment:
      - DATABASE_URL=${{DATABASE_URL:-}}
    volumes:
      - {volume_mount}
      - ./logs:/var/log/app
    networks:
      - controlbox
      - site_network
    labels:
{label_lines}
"""

        compose = f"""services:
{service_yaml}
networks:
  controlbox:
    external: true
  site_network:
    driver: bridge
"""
        compose_path = site_path / "docker-compose.yml"
        compose_path.write_text(compose, encoding="utf-8")
        return compose_path

    def _build_traefik_labels(self, website: Website, port: int) -> dict[str, str]:
        router_name = f"site-{str(website.id).split('-')[0]}"
        labels = {
            "traefik.enable": "true",
            f"traefik.http.routers.{router_name}.rule": f"Host(`{website.domain}`)",
            f"traefik.http.routers.{router_name}.entrypoints": "websecure",
            f"traefik.http.routers.{router_name}.tls.certresolver": "letsencrypt",
            f"traefik.http.services.{router_name}.loadbalancer.server.port": str(port),
        }
        if website.ssl_enabled:
            labels[f"traefik.http.routers.{router_name}.tls"] = "true"
        return labels

    def _format_env(self, database_config: dict) -> str:
        lines = []
        for key, value in database_config.items():
            if key not in ("password", "status", "engine") and value is not None:
                lines.append(f"{key.upper()}={value}")
        if database_config.get("connection_url"):
            lines.append(f"DATABASE_URL={database_config['connection_url']}")
        return "\n".join(lines) + "\n"

    async def _run_compose(self, compose_path: Path, container_name: str) -> str:
        safe_name = validate_container_name(container_name)
        await self._exec("docker", "compose", "-f", str(compose_path), "up", "-d", "--build")
        result = await self._exec("docker", "ps", "-q", "-f", f"name={safe_name}")
        return result.strip() or safe_name

    async def _exec(self, *args: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=docker_subprocess_env(self._settings),
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode() or stdout.decode() or f"Command failed: {' '.join(args)}")
        return stdout.decode()


class DatabaseProvisioner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def provision(self, website: Website) -> dict:
        engine = website.database_engine
        if engine == DatabaseEngine.NONE:
            return {}

        db_name = f"site_{str(website.id).replace('-', '_')[:16]}"
        db_user = f"u_{str(website.id).split('-')[0]}"
        db_password = secrets.token_urlsafe(24)

        if engine == DatabaseEngine.MYSQL:
            return {
                "engine": "mysql",
                "database_name": db_name,
                "username": db_user,
                "password": db_password,
                "host": self._settings.mysql_host,
                "port": self._settings.mysql_port,
                "connection_url": f"mysql://{db_user}:{db_password}@{self._settings.mysql_host}:{self._settings.mysql_port}/{db_name}",
                "status": "provisioned",
            }
        if engine == DatabaseEngine.SUPABASE:
            return {
                "engine": "supabase",
                "database_name": db_name,
                "username": db_user,
                "password": db_password,
                "host": self._settings.supabase_db_host,
                "port": self._settings.supabase_db_port,
                "connection_url": f"postgresql://{db_user}:{db_password}@{self._settings.supabase_db_host}:{self._settings.supabase_db_port}/{db_name}",
                "status": "provisioned",
            }
        if engine == DatabaseEngine.MSSQL:
            return {
                "engine": "mssql",
                "database_name": db_name,
                "username": db_user,
                "password": db_password,
                "host": self._settings.mssql_host,
                "port": self._settings.mssql_port,
                "connection_url": f"mssql+pyodbc://{db_user}:{db_password}@{self._settings.mssql_host}:{self._settings.mssql_port}/{db_name}",
                "status": "provisioned",
            }
        return {}
