"""Add min_stock columns to product table

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("product", sa.Column("min_stock", sa.Float, nullable=True))
    op.add_column("product", sa.Column("min_stock_unit", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("product", "min_stock_unit")
    op.drop_column("product", "min_stock")
