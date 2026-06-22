"""Read SSL certificate expiry from Traefik ACME storage."""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.backends import default_backend

from controlbox.config.settings import Settings

logger = logging.getLogger("controlbox.ssl")


def _acme_file(settings: Settings) -> Path:
    candidates = [
        Path("/host/var/lib/controlbox/letsencrypt/acme.json"),
        Path("/var/lib/controlbox/letsencrypt/acme.json"),
    ]
    raw = getattr(settings, "controlbox_data_dir", "") or ""
    if raw:
        base = Path(raw.replace("/host", "") if raw.startswith("/host/") else raw)
        candidates.insert(0, base / "letsencrypt" / "acme.json")
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


@lru_cache(maxsize=1)
def _load_domain_expiry_cache(acme_path: str, mtime: float) -> dict[str, int]:
    _ = mtime
    path = Path(acme_path)
    if not path.is_file():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.debug("Could not read acme.json", exc_info=True)
        return {}

    result: dict[str, int] = {}
    now = datetime.now(timezone.utc)

    for resolver_data in data.values():
        if not isinstance(resolver_data, dict):
            continue
        for entry in resolver_data.get("Certificates", []):
            if not isinstance(entry, dict):
                continue
            domain_info = entry.get("domain") or {}
            domains: list[str] = []
            main = domain_info.get("main")
            if main:
                domains.append(str(main).lower())
            for san in domain_info.get("sans") or []:
                domains.append(str(san).lower())

            cert_pem = entry.get("certificate")
            if not cert_pem:
                continue
            try:
                pem = base64.b64decode(cert_pem).decode("utf-8", errors="ignore")
                if "-----BEGIN" not in pem:
                    pem = f"-----BEGIN CERTIFICATE-----\n{pem}\n-----END CERTIFICATE-----\n"
                cert = x509.load_pem_x509_certificate(pem.encode("utf-8"), default_backend())
                expires = cert.not_valid_after
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                days = max(0, (expires - now).days)
                for domain in domains:
                    result[domain] = days
            except Exception:
                logger.debug("Could not parse certificate for %s", domains, exc_info=True)
    return result


class SslCertificateService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._path = _acme_file(settings)

    def days_remaining(self, domain: str) -> int | None:
        domain = domain.strip().lower()
        if not domain:
            return None
        try:
            mtime = self._path.stat().st_mtime if self._path.is_file() else 0.0
        except OSError:
            mtime = 0.0
        cache = _load_domain_expiry_cache(str(self._path), mtime)
        if domain in cache:
            return cache[domain]
        if domain.startswith("www."):
            return cache.get(domain[4:])
        return cache.get(f"www.{domain}")
