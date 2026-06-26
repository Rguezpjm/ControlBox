"""remove unique constraint on tenant_id for multi-tenant email

Revision ID: 024
Revises: 023
Create Date: 2025-06-26 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_tenant_mail_services_tenant_id", table_name="tenant_mail_services")
    op.create_index("ix_tenant_mail_services_tenant_id", "tenant_mail_services", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tenant_mail_services_tenant_id", table_name="tenant_mail_services")
    op.create_index("ix_tenant_mail_services_tenant_id", "tenant_mail_services", ["tenant_id"], unique=True)
