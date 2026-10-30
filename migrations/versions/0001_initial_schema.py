"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-02-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("barcode", sa.String(50), unique=True, nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("default_unit", sa.String(20), server_default="g"),
        sa.Column("nutrition_per_100_json", sa.Text, nullable=True),
        sa.Column("typical_pack_sizes_json", sa.Text, nullable=True),
        sa.Column("shelf_life_type", sa.String(10), server_default="MHD"),
        sa.Column("shelf_life_days_default", sa.Integer, nullable=True),
        sa.Column("image_url", sa.Text, nullable=True),
        sa.Column("synonyms_json", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "stock_entry",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("product.id"), nullable=False),
        sa.Column("quantity", sa.Float, nullable=False),
        sa.Column("unit", sa.String(20), server_default="g"),
        sa.Column("mhd", sa.Date, nullable=True),
        sa.Column("purchase_date", sa.Date, nullable=True),
        sa.Column("location", sa.String(50), server_default="Vorratskammer"),
        sa.Column("lot_note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("opened_at", sa.Date, nullable=True),
    )

    op.create_table(
        "consumption_event",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "stock_entry_id", sa.Integer, sa.ForeignKey("stock_entry.id"), nullable=False
        ),
        sa.Column("amount", sa.Float, nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("consumed_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("reason", sa.String(20), server_default="verbraucht"),
        sa.Column("source", sa.String(20), server_default="manual"),
        sa.Column("ref_type", sa.String(50), nullable=True),
        sa.Column("ref_id", sa.Integer, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("consumption_event")
    op.drop_table("stock_entry")
    op.drop_table("product")
