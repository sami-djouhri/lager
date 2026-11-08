"""Einband am Stueck (Buecher)

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-07

Owner 2026-11-07: im Einbuch-Lauf der Lager-App Hardcover, Taschenbuch usw. am
Stueck festhalten. Der Einband gehoert dem Stueck, nicht dem Titel (medien
`felder.py`: zwei Einbaende sind dasselbe Buch); medien liest ihn ueber den Spiegel.
"""

from alembic import op
import sqlalchemy as sa


revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sache") as b:
        b.add_column(sa.Column("einband", sa.String(30), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sache") as b:
        b.drop_column("einband")
