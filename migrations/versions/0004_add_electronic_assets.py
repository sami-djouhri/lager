"""add electronic assets

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "electronic_asset",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("brand", sa.String(length=100), nullable=True),
        sa.Column("model", sa.String(length=150), nullable=True),
        sa.Column("serial", sa.String(length=150), nullable=True),
        sa.Column("barcode", sa.String(length=50), nullable=True),
        sa.Column("condition", sa.String(length=30), nullable=False, server_default="gut"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="aktiv"),
        sa.Column("location", sa.String(length=80), nullable=False, server_default="Elektronik"),
        sa.Column("usage_status", sa.String(length=30), nullable=False, server_default="reserve"),
        sa.Column("homelab_role", sa.String(length=100), nullable=True),
        sa.Column("host_name", sa.String(length=100), nullable=True),
        sa.Column("service_refs_json", sa.Text(), nullable=True),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("purchase_price", sa.Float(), nullable=True),
        sa.Column("purchase_source", sa.String(length=100), nullable=True),
        sa.Column("purchase_url", sa.Text(), nullable=True),
        sa.Column("warranty_end", sa.Date(), nullable=True),
        sa.Column("estimated_resale_value", sa.Float(), nullable=True),
        sa.Column("resale_confidence", sa.String(length=30), nullable=True),
        sa.Column("sell_decision", sa.String(length=30), nullable=False, server_default="behalten"),
        sa.Column("sell_reason", sa.Text(), nullable=True),
        sa.Column("desired_min_profit", sa.Float(), nullable=True),
        sa.Column("manual_pin", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ebay_item_id", sa.String(length=100), nullable=True),
        sa.Column("ebay_watch_query", sa.String(length=250), nullable=True),
        sa.Column("external_refs_json", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("serial", name="uq_electronic_asset_serial"),
        sa.UniqueConstraint("barcode", name="uq_electronic_asset_barcode"),
    )
    op.create_index("ix_electronic_asset_name", "electronic_asset", ["name"])
    op.create_index("ix_electronic_asset_category", "electronic_asset", ["category"])
    op.create_index("ix_electronic_asset_condition", "electronic_asset", ["condition"])
    op.create_index("ix_electronic_asset_status", "electronic_asset", ["status"])
    op.create_index("ix_electronic_asset_usage_status", "electronic_asset", ["usage_status"])
    op.create_index("ix_electronic_asset_homelab_role", "electronic_asset", ["homelab_role"])
    op.create_index("ix_electronic_asset_host_name", "electronic_asset", ["host_name"])
    op.create_index("ix_electronic_asset_sell_decision", "electronic_asset", ["sell_decision"])
    op.create_index("ix_electronic_asset_ebay_item_id", "electronic_asset", ["ebay_item_id"])


def downgrade() -> None:
    op.drop_table("electronic_asset")
