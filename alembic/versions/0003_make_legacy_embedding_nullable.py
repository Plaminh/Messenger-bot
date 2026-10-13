"""Allow text-only memories while preserving legacy vectors.

Revision ID: 0003_embedding_nullable
Revises: 0002_last_extracted_msg
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = "0003_embedding_nullable"
down_revision: Union[str, None] = "0002_last_extracted_msg"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("memories", "embedding", existing_type=Vector(384), nullable=True)


def downgrade() -> None:
    # This intentionally fails if text-only rows exist instead of deleting data.
    op.alter_column("memories", "embedding", existing_type=Vector(384), nullable=False)
