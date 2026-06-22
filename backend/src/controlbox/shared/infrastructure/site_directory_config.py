"""Site directory settings — nginx root, open_basedir, auth, subdirectory bindings."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

MAX_SUBDIR_SCAN = 64


def build_htpasswd_line(username: str, password: str) -> str:
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


def normalize_running_directory(value: str) -> str:
    cleaned = (value or "/").replace("\\", "/").strip()
    if not cleaned or cleaned == ".":
        return "/"
    if not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"
    return cleaned.rstrip("/") if cleaned != "/" else "/"


def resolve_host_web_root(site_directory: Path, running_directory: str) -> Path:
    rel = normalize_running_directory(running_directory)
    if rel == "/":
        return site_directory
    sub = rel.lstrip("/")
    return (site_directory / sub).resolve()


def container_web_root(site_directory: Path, running_directory: str, mount_path: Path) -> str:
    """Map host site directory + running dir to in-container nginx root."""
    host_root = resolve_host_web_root(site_directory, running_directory)
    rel = host_root.relative_to(site_directory.resolve())
    rel_posix = rel.as_posix()
    if rel_posix == ".":
        return mount_path.as_posix()
    return f"{mount_path.as_posix()}/{rel_posix}"


def list_running_directory_options(site_directory: Path, max_depth: int = 3) -> list[str]:
    options = ["/"]
    if not site_directory.is_dir():
        return options
    base = site_directory.resolve()
    try:
        for path in sorted(base.rglob("*")):
            if not path.is_dir():
                continue
            rel = path.relative_to(base)
            if len(rel.parts) > max_depth:
                continue
            options.append(f"/{rel.as_posix()}")
            if len(options) >= MAX_SUBDIR_SCAN:
                break
    except OSError:
        pass
    return list(dict.fromkeys(options))


def validate_site_directory(site_path: Path, document_root: str) -> Path:
    candidate = Path(document_root).resolve()
    root = site_path.resolve()
    if not str(candidate).startswith(str(root)):
        raise ValueError("Site directory must stay inside the site folder")
    if not candidate.is_dir():
        raise ValueError("Site directory does not exist")
    return candidate


def _index_directive(index_files: list[str]) -> str:
    files = index_files or ["index.php", "index.html", "index.htm"]
    return " ".join(files)


def _auth_block(enabled: bool) -> str:
    if not enabled:
        return ""
    return """
    auth_basic "Restricted";
    auth_basic_user_file /etc/nginx/.htpasswd;
"""


def _server_block(
    *,
    server_name: str,
    root: str,
    index_files: list[str],
    logs_enabled: bool,
    auth_enabled: bool,
    extra_locations: str = "",
) -> str:
    access_log = (
        "access_log /var/log/nginx/access.log combined;"
        if logs_enabled
        else "access_log off;"
    )
    auth = _auth_block(auth_enabled)
    index = _index_directive(index_files)
    return f"""server {{
    listen 80;
    server_name {server_name};
    root {root};
    index {index};
    client_max_body_size 128M;

    {access_log}
    error_log /var/log/nginx/error.log warn;
{auth}
    location / {{
        try_files $uri $uri/ /index.php?$args;
    }}

    location ~ \\.php$ {{
        fastcgi_pass php:9000;
        fastcgi_index index.php;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        include fastcgi_params;
        fastcgi_read_timeout 300;
    }}

    location ~ /\\.ht {{
        deny all;
    }}

    location = /favicon.ico {{
        log_not_found off;
        access_log off;
    }}
{extra_locations}
}}
"""


def render_wordpress_nginx(settings: dict[str, Any], site_directory: Path) -> str:
    running_directory = normalize_running_directory(str(settings.get("running_directory") or "/"))
    index_files = list(settings.get("index_files") or ["index.php", "index.html", "index.htm"])
    logs_enabled = settings.get("logs_enabled", True) is not False
    auth_enabled = bool(settings.get("limit_access_enabled"))

    root = container_web_root(site_directory, running_directory, Path("/var/www/html"))
    blocks = [
        _server_block(
            server_name="_",
            root=root,
            index_files=index_files,
            logs_enabled=logs_enabled,
            auth_enabled=auth_enabled,
        )
    ]

    for binding in settings.get("subdirectory_bindings") or []:
        domain = str(binding.get("domain") or "").strip().lower()
        directory = normalize_running_directory(str(binding.get("directory") or "/"))
        if not domain:
            continue
        binding_root = container_web_root(site_directory, directory, Path("/var/www/html"))
        blocks.append(
            _server_block(
                server_name=domain,
                root=binding_root,
                index_files=index_files,
                logs_enabled=logs_enabled,
                auth_enabled=auth_enabled,
            )
        )

    return "\n\n".join(blocks) + "\n"


def render_php_open_basedir_ini(enabled: bool, web_root: str) -> str:
    if not enabled:
        return "; open_basedir disabled\n"
    base = web_root.rstrip("/")
    return f"""; ControlBox open_basedir
php_admin_value[open_basedir] = {base}/:/tmp/:/proc/
"""


def write_directory_security_files(
    site_path: Path,
    settings: dict[str, Any],
    *,
    site_directory: Path,
    mount_path: Path,
) -> None:
    nginx_dir = site_path / "nginx"
    nginx_dir.mkdir(parents=True, exist_ok=True)

    running_directory = normalize_running_directory(str(settings.get("running_directory") or "/"))
    web_root = container_web_root(site_directory, running_directory, mount_path)
    open_basedir_enabled = settings.get("open_basedir_enabled", True) is not False
    (nginx_dir / "php-security.ini").write_text(
        render_php_open_basedir_ini(open_basedir_enabled, web_root),
        encoding="utf-8",
    )

    if settings.get("limit_access_enabled"):
        user = str(settings.get("limit_access_user") or "admin").strip() or "admin"
        password = str(settings.get("limit_access_password") or "").strip()
        htpasswd_path = nginx_dir / ".htpasswd"
        if password:
            htpasswd_path.write_text(
                build_htpasswd_line(user, password) + "\n",
                encoding="utf-8",
            )
        elif not htpasswd_path.is_file():
            htpasswd_path.write_text("blocked:blocked\n", encoding="utf-8")
    else:
        (nginx_dir / ".htpasswd").write_text("blocked:blocked\n", encoding="utf-8")


def patch_wordpress_compose_bindings(compose_text: str, bindings: list[dict[str, Any]], router_prefix: str) -> str:
    """Append Traefik routers for subdirectory-bound domains on the nginx service."""
    binding_domains = sorted({
        str(b.get("domain") or "").strip().lower()
        for b in bindings
        if str(b.get("domain") or "").strip()
    })

    lines = compose_text.splitlines()
    filtered: list[str] = []
    skip_prefix = f"traefik.http.routers.{router_prefix}-bind-"
    in_nginx = False
    nginx_labels_ended = False
    insert_at: int | None = None

    for line in lines:
        if skip_prefix in line:
            continue
        stripped = line.strip()
        if stripped.startswith("nginx:"):
            in_nginx = True
        elif in_nginx and not nginx_labels_ended and stripped and not stripped.startswith("-") and not stripped.startswith("#"):
            if not stripped.startswith("labels:") and "labels:" not in stripped:
                in_nginx = False
        if in_nginx and stripped == "labels:":
            insert_at = None
        if in_nginx and stripped.startswith("- ") and "traefik.http.routers." in stripped:
            insert_at = len(filtered) + 1
        if in_nginx and insert_at is not None and stripped.startswith("depends_on:"):
            nginx_labels_ended = True
        filtered.append(line)

    extra: list[str] = []
    for idx, domain in enumerate(binding_domains):
        router = f"{router_prefix}-bind-{idx}"
        extra.extend([
            f'      - "traefik.http.routers.{router}.rule=Host(`{domain}`)"',
            f'      - "traefik.http.routers.{router}.entrypoints=websecure"',
            f'      - "traefik.http.routers.{router}.tls=true"',
            f'      - "traefik.http.routers.{router}.tls.certresolver=letsencrypt"',
            f'      - "traefik.http.routers.{router}.service={router_prefix}"',
        ])

    if extra and insert_at is not None:
        filtered[insert_at:insert_at] = extra

    return "\n".join(filtered) + ("\n" if compose_text.endswith("\n") else "")


def write_php_htaccess_security(public_dir: Path, enabled: bool, container_root: str) -> None:
    public_dir.mkdir(parents=True, exist_ok=True)
    htaccess = public_dir / ".htaccess"
    marker_start = "# CONTROLBOX_OPEN_BASEDIR_START"
    marker_end = "# CONTROLBOX_OPEN_BASEDIR_END"
    existing = htaccess.read_text(encoding="utf-8", errors="replace") if htaccess.is_file() else ""
    cleaned_lines: list[str] = []
    skipping = False
    for line in existing.splitlines():
        if line.strip() == marker_start:
            skipping = True
            continue
        if line.strip() == marker_end:
            skipping = False
            continue
        if not skipping:
            cleaned_lines.append(line)
    base = cleaned_lines
    if enabled:
        block = [
            marker_start,
            f"php_value open_basedir {container_root.rstrip('/')}/:/tmp/",
            marker_end,
        ]
        content = "\n".join([*base, *block]).strip() + "\n"
    else:
        content = "\n".join(base).strip()
        content = (content + "\n") if content else ""
    htaccess.write_text(content, encoding="utf-8")
