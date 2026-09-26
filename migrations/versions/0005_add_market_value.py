"""add market value columns to electronic_asset

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-03
"""

from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Marktwert (marktwatch-Median) getrennt von estimated_resale_value (manuell):
    # zwei Quellen, zwei Spalten: nie gegenseitig überschreiben.
    op.add_column("electronic_asset", sa.Column("market_value_eur", sa.Float(), nullable=True))
    op.add_column("electronic_asset", sa.Column("market_value_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("electronic_asset", "market_value_at")
    op.drop_column("electronic_asset", "market_value_eur")
