"""Map site directories to domain labels for the file manager (aaPanel-style wwwroot view)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.infrastructure.resource_isolation import HasAccessContext, is_owner_visible


@dataclass(frozen=True)
class SiteFolder:
    path: str
    domain: str
    site_type: str


def _domain_label(name: str, domain: str, *, fallback: str) -> str:
    dom = (domain or "").strip()
    if dom:
        return dom
    return (name or "").strip() or fallback


async def list_site_folders(
    uow: UnitOfWork,
    context: HasAccessContext,
    tenant_id: UUID,
) -> list[SiteFolder]:
    folders: list[SiteFolder] = []

    async with uow:
        websites = await uow.websites.list_by_tenant(tenant_id, limit=500, offset=0)
        for site in websites:
            if not is_owner_visible(context, site.owner_user_id):
                continue
            folders.append(
                SiteFolder(
                    path=str(site.id),
                    domain=_domain_label(site.name, site.domain, fallback="website"),
                    site_type="website",
                )
            )

        wp_sites = await uow.wordpress_sites.list_by_tenant(tenant_id, limit=500, offset=0)
        for site in wp_sites:
            if not is_owner_visible(context, site.owner_user_id):
                continue
            folders.append(
                SiteFolder(
                    path=f"wordpress/{site.id}",
                    domain=_domain_label(site.name, site.domain, fallback="wordpress"),
                    site_type="wordpress",
                )
            )

    folders.sort(key=lambda item: item.domain.lower())
    return folders


async def build_path_labels(
    uow: UnitOfWork,
    context: HasAccessContext,
    tenant_id: UUID | None,
) -> dict[str, str]:
    if tenant_id is None:
        return {}
    folders = await list_site_folders(uow, context, tenant_id)
    return {folder.path: folder.domain for folder in folders}


async def build_folder_display_names(
    uow: UnitOfWork,
    context: HasAccessContext,
    tenant_scope: UUID | None,
    path: str,
) -> dict[str, str]:
    """Map filesystem entry names in the current directory to display labels."""
    parts = [part for part in path.replace("\\", "/").strip("/").split("/") if part]
    labels: dict[str, str] = {}

    if tenant_scope is not None:
        if parts:
            tenant_id = tenant_scope
            site_labels = await build_path_labels(uow, context, tenant_id)
            if parts == ["wordpress"]:
                for rel_path, domain in site_labels.items():
                    if rel_path.startswith("wordpress/"):
                        labels[rel_path.split("/", 1)[1]] = domain
            return labels
        tenant_id = tenant_scope
    elif not parts:
        async with uow:
            tenant_ids = await uow.tenants.list_active_ids()
            for tenant_id in tenant_ids:
                tenant = await uow.tenants.get_by_id(tenant_id)
                if tenant:
                    labels[str(tenant_id)] = tenant.name or tenant.slug or str(tenant_id)
        return labels
    elif len(parts) == 1:
        try:
            tenant_id = UUID(parts[0])
        except ValueError:
            return labels
    else:
        return labels

    site_labels = await build_path_labels(uow, context, tenant_id)
    for rel_path, domain in site_labels.items():
        if "/" not in rel_path:
            labels[rel_path] = domain

    return labels
