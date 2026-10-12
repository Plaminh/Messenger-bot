"""Add users.last_extracted_message_id (memory extractor watermark)

Revision ID: 0002_last_extracted_msg
Revises: 0001_initial_schema
Create Date: 2026-10-13 09:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_last_extracted_msg"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("last_extracted_message_id", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "last_extracted_message_id")
