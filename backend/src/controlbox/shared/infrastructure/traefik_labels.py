"""Traefik Docker label helpers (Let's Encrypt + HTTP→HTTPS redirect)."""

from __future__ import annotations

import re

HTTPS_REDIRECT_MIDDLEWARE = "https-redirect@file"

_ROUTER_RULE_RE = re.compile(
    r'traefik\.http\.routers\.([^."]+)\.rule=Host\(`([^`]+)`\)'
)


def traefik_router_labels(
    router_name: str,
    domain: str,
    port: int,
    *,
    ssl_enabled: bool = True,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    labels = {
        "traefik.enable": "true",
        f"traefik.http.routers.{router_name}.rule": f"Host(`{domain}`)",
        f"traefik.http.services.{router_name}.loadbalancer.server.port": str(port),
    }
    if ssl_enabled:
        labels[f"traefik.http.routers.{router_name}.entrypoints"] = "websecure"
        labels[f"traefik.http.routers.{router_name}.tls"] = "true"
        labels[f"traefik.http.routers.{router_name}.tls.certresolver"] = "letsencrypt"
        http_router = f"{router_name}-http"
        labels[f"traefik.http.routers.{http_router}.rule"] = f"Host(`{domain}`)"
        labels[f"traefik.http.routers.{http_router}.entrypoints"] = "web"
        labels[f"traefik.http.routers.{http_router}.middlewares"] = HTTPS_REDIRECT_MIDDLEWARE
        labels[f"traefik.http.routers.{http_router}.service"] = router_name
    else:
        labels[f"traefik.http.routers.{router_name}.entrypoints"] = "web"
    if extra:
        labels.update(extra)
    return labels


def compose_label_lines(labels: dict[str, str]) -> list[str]:
    return [f'      - "{key}={value}"' for key, value in labels.items()]


def parse_compose_router_domains(compose_text: str) -> dict[str, str]:
    domains: dict[str, str] = {}
    for line in compose_text.splitlines():
        match = _ROUTER_RULE_RE.search(line.replace(" ", ""))
        if not match:
            match = re.search(r'traefik\.http\.routers\.([^."]+)\.rule=Host\(`([^`]+)`\)', line)
        if match:
            router, domain = match.group(1), match.group(2)
            if not router.endswith("-http"):
                domains[router] = domain
    return domains


def append_https_redirect_labels(
    compose_lines: list[str],
    router_domains: dict[str, str],
) -> list[str]:
    if not router_domains:
        return compose_lines

    filtered = [
        line
        for line in compose_lines
        if "-http.rule=Host" not in line.replace(" ", "")
        and "-http.entrypoints=web" not in line.replace(" ", "")
        and "-http.middlewares=https-redirect" not in line.replace(" ", "")
        and "-http.service=" not in line.replace(" ", "")
    ]

    insert_idx = len(filtered)
    for idx, line in enumerate(filtered):
        if "labels:" in line:
            insert_idx = idx + 1
            break

    extra: list[str] = []
    for router, domain in sorted(router_domains.items()):
        http_router = f"{router}-http"
        extra.extend(
            compose_label_lines(
                {
                    f"traefik.http.routers.{http_router}.rule": f"Host(`{domain}`)",
                    f"traefik.http.routers.{http_router}.entrypoints": "web",
                    f"traefik.http.routers.{http_router}.middlewares": HTTPS_REDIRECT_MIDDLEWARE,
                    f"traefik.http.routers.{http_router}.service": router,
                }
            )
        )

    if extra:
        filtered[insert_idx:insert_idx] = extra
    return filtered
