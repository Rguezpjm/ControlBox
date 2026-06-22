from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status

from controlbox.modules.dns.infrastructure.api_keys import verify_api_key
from controlbox.modules.identity.api.dependencies import get_unit_of_work
from controlbox.shared.application.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class IntegrationContext:
    tenant_id: UUID
    api_key_id: UUID
    scopes: list[str]


async def get_integration_context(
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> IntegrationContext:
    api_key_value = x_api_key
    if not api_key_value and authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            api_key_value = parts[1]

    if not api_key_value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required")

    if not api_key_value.startswith("cbdns_"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key format")

    parts = api_key_value.split("_", 2)
    if len(parts) < 3:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key format")

    prefix = parts[1]
    stored = await uow.dns_api_keys.get_by_prefix(prefix)
    if not stored or not stored.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    if not verify_api_key(api_key_value, stored.key_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    stored.mark_used()

    return IntegrationContext(
        tenant_id=stored.tenant_id,
        api_key_id=stored.id,
        scopes=stored.scopes,
    )


def require_scope(scope: str):
    async def _check(context: Annotated[IntegrationContext, Depends(get_integration_context)]) -> IntegrationContext:
        if scope not in context.scopes and "dns.manage" not in context.scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Scope '{scope}' required")
        return context
    return _check
