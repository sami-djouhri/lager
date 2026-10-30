"""Add indexes for query performance

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-05
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("idx_stock_entry_product_id", "stock_entry", ["product_id"])
    op.create_index("idx_stock_entry_mhd", "stock_entry", ["mhd"])
    op.create_index("idx_stock_entry_quantity", "stock_entry", ["quantity"])
    op.create_index("idx_consumption_event_stock_entry_id", "consumption_event", ["stock_entry_id"])
    op.create_index("idx_consumption_event_consumed_at", "consumption_event", ["consumed_at"])


def downgrade() -> None:
    op.drop_index("idx_consumption_event_consumed_at")
    op.drop_index("idx_consumption_event_stock_entry_id")
    op.drop_index("idx_stock_entry_quantity")
    op.drop_index("idx_stock_entry_mhd")
    op.drop_index("idx_stock_entry_product_id")
