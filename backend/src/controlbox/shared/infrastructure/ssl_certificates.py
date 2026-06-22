"""Read SSL certificate expiry from Traefik ACME storage."""

from __future__ import annotations

import base64
import json
import logging
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.backends import default_backend

from controlbox.config.settings import Settings

logger = logging.getLogger("controlbox.ssl")


def _path_is_readable_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _acme_file(settings: Settings) -> Path:
    candidates = [
        Path("/etc/controlbox/letsencrypt/acme.json"),
        Path("/host/var/lib/controlbox/letsencrypt/acme.json"),
        Path("/var/lib/controlbox/letsencrypt/acme.json"),
    ]
    raw = getattr(settings, "controlbox_data_dir", "") or ""
    if raw:
        base = Path(raw.replace("/host", "") if raw.startswith("/host/") else raw)
        candidates.insert(0, base / "letsencrypt" / "acme.json")
    for path in candidates:
        if _path_is_readable_file(path):
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

        custom_days = self._custom_cert_days(domain)
        if custom_days is not None:
            return custom_days

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

    def _custom_cert_days(self, domain: str) -> int | None:
        data_dir = getattr(self._settings, "controlbox_data_dir", "") or "/var/lib/controlbox"
        certs_root = Path(data_dir.replace("/host", "") if data_dir.startswith("/host/") else data_dir) / "certs"
        if not certs_root.is_dir():
            return None
        now = datetime.now(timezone.utc)
        for cert_file in certs_root.rglob("cert.pem"):
            try:
                pem = cert_file.read_text(encoding="utf-8", errors="replace")
                for block in re.findall(
                    r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
                    pem,
                    re.DOTALL,
                ):
                    cert = x509.load_pem_x509_certificate(block.encode("utf-8"), default_backend())
                    names: list[str] = []
                    try:
                        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
                        names = [str(n.value).lower() for n in san.value]
                    except x509.ExtensionNotFound:
                        cn = cert.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)
                        if cn:
                            names = [str(cn[0].value).lower()]
                    if domain not in names and f"www.{domain}" not in names:
                        continue
                    expires = getattr(cert, "not_valid_after_utc", cert.not_valid_after)
                    if expires.tzinfo is None:
                        expires = expires.replace(tzinfo=timezone.utc)
                    return max(0, (expires - now).days)
            except Exception:
                continue
        return None
