"""resource owner scope columns

Revision ID: 021
Revises: 020
Create Date: 2026-06-23 13:55:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)
    op.add_column("websites", sa.Column("owner_user_id", uuid_type, nullable=True))
    op.add_column("wordpress_sites", sa.Column("owner_user_id", uuid_type, nullable=True))
    op.add_column("managed_databases", sa.Column("owner_user_id", uuid_type, nullable=True))
    op.add_column("ftp_accounts", sa.Column("owner_user_id", uuid_type, nullable=True))

    op.create_foreign_key(
        "fk_websites_owner_user_id_users",
        "websites",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_wordpress_sites_owner_user_id_users",
        "wordpress_sites",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_managed_databases_owner_user_id_users",
        "managed_databases",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_ftp_accounts_owner_user_id_users",
        "ftp_accounts",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index("ix_websites_owner_user_id", "websites", ["owner_user_id"])
    op.create_index("ix_wordpress_sites_owner_user_id", "wordpress_sites", ["owner_user_id"])
    op.create_index("ix_managed_databases_owner_user_id", "managed_databases", ["owner_user_id"])
    op.create_index("ix_ftp_accounts_owner_user_id", "ftp_accounts", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index("ix_ftp_accounts_owner_user_id", table_name="ftp_accounts")
    op.drop_index("ix_managed_databases_owner_user_id", table_name="managed_databases")
    op.drop_index("ix_wordpress_sites_owner_user_id", table_name="wordpress_sites")
    op.drop_index("ix_websites_owner_user_id", table_name="websites")

    op.drop_constraint("fk_ftp_accounts_owner_user_id_users", "ftp_accounts", type_="foreignkey")
    op.drop_constraint("fk_managed_databases_owner_user_id_users", "managed_databases", type_="foreignkey")
    op.drop_constraint("fk_wordpress_sites_owner_user_id_users", "wordpress_sites", type_="foreignkey")
    op.drop_constraint("fk_websites_owner_user_id_users", "websites", type_="foreignkey")

    op.drop_column("ftp_accounts", "owner_user_id")
    op.drop_column("managed_databases", "owner_user_id")
    op.drop_column("wordpress_sites", "owner_user_id")
    op.drop_column("websites", "owner_user_id")
