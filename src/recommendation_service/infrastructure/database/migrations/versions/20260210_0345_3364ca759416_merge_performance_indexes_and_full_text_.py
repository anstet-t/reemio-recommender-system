"""merge performance indexes and full-text search migrations

Revision ID: 3364ca759416
Revises: a3f1c8d92e47, b7e2f4a19c83
Create Date: 2026-02-10 03:45:01.145591+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '3364ca759416'
down_revision: Union[str, None] = ('a3f1c8d92e47', 'b7e2f4a19c83')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
