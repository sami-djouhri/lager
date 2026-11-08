"""add bereich to product

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-01
"""

from alembic import op
import sqlalchemy as sa


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Owner 2026-11-01: das Lager fuehrt mehr als Lebensmittel, getrennt nach
    # festen Bereichen (app/bereiche.py). Alles Bisherige war Lebensmittel.
    # Spalte anhaengen statt Tabelle neu bauen: SQLite kann ADD COLUMN mit
    # Vorgabewert, und batch_alter_table wuerde die Uniques aus 0006 umkopieren.
    op.add_column(
        "product",
        sa.Column("bereich", sa.String(20), nullable=False, server_default="lebensmittel"),
    )
    op.create_index("ix_product_bereich", "product", ["bereich"])


def downgrade() -> None:
    op.drop_index("ix_product_bereich", table_name="product")
    with op.batch_alter_table("product") as batch:
        batch.drop_column("bereich")
