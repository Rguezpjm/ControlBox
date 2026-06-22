"""Deploy third-party SSL certificates (Cloudflare Origin, commercial CA, etc.) via Traefik."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ec, ed25519, dsa

from controlbox.config.settings import Settings

logger = logging.getLogger("controlbox.ssl.custom")

_PEM_CERT_RE = re.compile(
    r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
    re.DOTALL,
)


def _resolve_data_dir(settings: Settings) -> Path:
    raw = (settings.controlbox_data_dir or "/var/lib/controlbox").strip()
    if raw.startswith("/host/"):
        return Path(raw)
    return Path(raw)


def _resolve_config_dir(settings: Settings) -> Path:
    raw = (settings.platform_config_dir or "/etc/controlbox").strip()
    if raw.startswith("/host/"):
        return Path(raw)
    return Path(raw)


def _normalize_pem(text: str, label: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError(f"{label} is required")
    if "-----BEGIN" not in cleaned:
        raise ValueError(f"{label} must be PEM format")
    return cleaned + ("\n" if not cleaned.endswith("\n") else "")


def _load_private_key(pem: str):
    try:
        return serialization.load_pem_private_key(pem.encode("utf-8"), password=None, backend=default_backend())
    except Exception as exc:
        raise ValueError("Invalid private key PEM") from exc


def _load_certificates(pem: str) -> list[x509.Certificate]:
    certs: list[x509.Certificate] = []
    for block in _PEM_CERT_RE.findall(pem):
        certs.append(x509.load_pem_x509_certificate(block.encode("utf-8"), default_backend()))
    if not certs:
        raise ValueError("Certificate PEM must contain at least one certificate block")
    return certs


def _cert_matches_key(cert: x509.Certificate, private_key) -> bool:
    cert_pub = cert.public_key()
    key_pub = private_key.public_key()
    if isinstance(cert_pub, rsa.RSAPublicKey) and isinstance(key_pub, rsa.RSAPublicKey):
        return cert_pub.public_numbers() == key_pub.public_numbers()
    if isinstance(cert_pub, ec.EllipticCurvePublicKey) and isinstance(key_pub, ec.EllipticCurvePublicKey):
        return cert_pub.public_numbers() == key_pub.public_numbers()
    if isinstance(cert_pub, ed25519.Ed25519PublicKey) and isinstance(key_pub, ed25519.Ed25519PublicKey):
        return cert_pub.public_bytes_raw() == key_pub.public_bytes_raw()
    if isinstance(cert_pub, dsa.DSAPublicKey) and isinstance(key_pub, dsa.DSAPublicKey):
        return cert_pub.public_numbers() == key_pub.public_numbers()
    return False


def _domain_matches_cert(domain: str, cert: x509.Certificate) -> bool:
    domain = domain.strip().lower()
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        names = {str(n.value).lower() for n in san.value}
        for name in names:
            if name == domain:
                return True
            if name.startswith("*.") and domain.endswith(name[1:]):
                return True
    except x509.ExtensionNotFound:
        pass
    cn = cert.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)
    if cn:
        cn_val = str(cn[0].value).lower()
        if cn_val == domain or (cn_val.startswith("*.") and domain.endswith(cn_val[1:])):
            return True
    return False


@dataclass
class CustomSslInfo:
    provider: str
    deployed: bool
    force_https: bool
    cert_type: str
    cert_brand: str
    cert_domains: list[str]
    expires_at: str | None
    days_remaining: int | None
    certificate_pem: str


class CustomSslManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._data_dir = _resolve_data_dir(settings)
        self._config_dir = _resolve_config_dir(settings)

    def cert_dir(self, site_type: str, site_id: UUID) -> Path:
        return self._data_dir / "certs" / site_type / str(site_id)

    def traefik_cert_path(self, site_type: str, site_id: UUID) -> tuple[str, str]:
        base = f"/certs/{site_type}/{site_id}"
        return f"{base}/cert.pem", f"{base}/key.pem"

    def get_ssl_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        ssl = dict(settings.get("ssl") or {})
        ssl.setdefault("provider", "letsencrypt")
        ssl.setdefault("force_https", True)
        return ssl

    def build_info(self, site_type: str, site_id: UUID, settings: dict[str, Any], primary_domain: str) -> CustomSslInfo:
        ssl = self.get_ssl_settings(settings)
        provider = str(ssl.get("provider") or "letsencrypt")
        cert_dir = self.cert_dir(site_type, site_id)
        cert_file = cert_dir / "cert.pem"
        deployed = provider == "custom" and cert_file.is_file()

        cert_pem = ""
        cert_type = "Let's Encrypt" if provider == "letsencrypt" else "Other certificate"
        cert_brand = ""
        cert_domains: list[str] = []
        expires_at: str | None = None
        days_remaining: int | None = None

        if deployed and cert_file.is_file():
            cert_pem = cert_file.read_text(encoding="utf-8", errors="replace")
            try:
                certs = _load_certificates(cert_pem)
                leaf = certs[0]
                issuer = leaf.issuer.get_attributes_for_oid(x509.oid.NameOID.ORGANIZATION_NAME)
                cert_brand = str(issuer[0].value) if issuer else leaf.issuer.rfc4514_string()
                try:
                    san = leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName)
                    cert_domains = [str(n.value) for n in san.value]
                except x509.ExtensionNotFound:
                    cn = leaf.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)
                    cert_domains = [str(cn[0].value)] if cn else [primary_domain]
                expires = getattr(leaf, "not_valid_after_utc", leaf.not_valid_after)
                expires_at = expires.date().isoformat()
                days_remaining = max(0, (expires - datetime.now(timezone.utc)).days)
            except Exception:
                logger.debug("Could not parse deployed certificate", exc_info=True)
                cert_domains = [primary_domain]
        elif provider == "letsencrypt":
            cert_domains = [primary_domain]

        return CustomSslInfo(
            provider=provider,
            deployed=deployed,
            force_https=bool(ssl.get("force_https", True)),
            cert_type=cert_type,
            cert_brand=cert_brand or ("Let's Encrypt" if provider == "letsencrypt" else "Third-party"),
            cert_domains=cert_domains or [primary_domain],
            expires_at=expires_at,
            days_remaining=days_remaining,
            certificate_pem=cert_pem,
        )

    def save_custom_certificate(
        self,
        site_type: str,
        site_id: UUID,
        primary_domain: str,
        certificate_pem: str,
        private_key_pem: str,
    ) -> None:
        cert_pem = _normalize_pem(certificate_pem, "Certificate")
        key_pem = _normalize_pem(private_key_pem, "Private key")
        private_key = _load_private_key(key_pem)
        certs = _load_certificates(cert_pem)
        if not _cert_matches_key(certs[0], private_key):
            raise ValueError("Private key does not match the certificate")

        domains = [primary_domain]
        if not _domain_matches_cert(primary_domain, certs[0]):
            logger.warning("Certificate SAN/CN may not include primary domain %s", primary_domain)

        cert_dir = self.cert_dir(site_type, site_id)
        cert_dir.mkdir(parents=True, exist_ok=True)
        (cert_dir / "cert.pem").write_text(cert_pem, encoding="utf-8")
        key_path = cert_dir / "key.pem"
        key_path.write_text(key_pem, encoding="utf-8")
        os.chmod(key_path, 0o600)
        os.chmod(cert_dir / "cert.pem", 0o644)
        self.sync_traefik_dynamic_config()

    def remove_custom_certificate(self, site_type: str, site_id: UUID) -> None:
        cert_dir = self.cert_dir(site_type, site_id)
        if cert_dir.is_dir():
            for f in cert_dir.iterdir():
                f.unlink(missing_ok=True)
            cert_dir.rmdir()
        self.sync_traefik_dynamic_config()

    def sync_traefik_dynamic_config(self) -> None:
        certs_root = self._data_dir / "certs"
        dynamic_dir = self._config_dir / "traefik" / "dynamic"
        dynamic_dir.mkdir(parents=True, exist_ok=True)
        target = dynamic_dir / "custom-certs.yml"

        entries: list[str] = []
        if certs_root.is_dir():
            for cert_file in sorted(certs_root.rglob("cert.pem")):
                key_file = cert_file.parent / "key.pem"
                if not key_file.is_file():
                    continue
                rel = cert_file.parent.relative_to(certs_root)
                traefik_cert = f"/certs/{rel.as_posix()}/cert.pem"
                traefik_key = f"/certs/{rel.as_posix()}/key.pem"
                entries.append(
                    f"    - certFile: {traefik_cert}\n      keyFile: {traefik_key}"
                )

        if entries:
            content = "tls:\n  certificates:\n" + "\n".join(entries) + "\n"
        else:
            content = "# No custom SSL certificates deployed\n"
        target.write_text(content, encoding="utf-8")

    def patch_compose_ssl(
        self,
        compose_text: str,
        router_prefix: str,
        *,
        ssl_enabled: bool,
        provider: str,
    ) -> str:
        lines = compose_text.splitlines()
        router_names: set[str] = set()
        for line in lines:
            if router_prefix not in line or "traefik.http.routers." not in line:
                continue
            match = re.search(rf"traefik\.http\.routers\.({re.escape(router_prefix)}[^.\"]+)", line)
            if match:
                router_names.add(match.group(1))

        out: list[str] = []
        for line in lines:
            if router_prefix in line and "tls.certresolver" in line:
                if provider == "custom" or not ssl_enabled:
                    continue
            if not ssl_enabled and router_prefix in line and ".tls=true" in line:
                continue
            out.append(line)

        if ssl_enabled and provider == "letsencrypt" and router_names:
            for router in sorted(router_names):
                resolver_line = f'      - "traefik.http.routers.{router}.tls.certresolver=letsencrypt"'
                if not any(f"routers.{router}.tls.certresolver" in line for line in out):
                    insert_idx = len(out)
                    for idx, line in enumerate(out):
                        if "labels:" in line:
                            insert_idx = idx + 1
                            break
                    out.insert(insert_idx, resolver_line)

        if ssl_enabled and provider == "custom" and router_names:
            for router in sorted(router_names):
                tls_line = f'      - "traefik.http.routers.{router}.tls=true"'
                if not any(f"routers.{router}.tls=true" in line for line in out):
                    insert_idx = len(out)
                    for idx, line in enumerate(out):
                        if "labels:" in line:
                            insert_idx = idx + 1
                            break
                    out.insert(insert_idx, tls_line)

        return "\n".join(out) + ("\n" if compose_text.endswith("\n") else "")
