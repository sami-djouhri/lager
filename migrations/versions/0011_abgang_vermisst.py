"""Abgang (Verkauft, Weg) und Vermisst fuer Sachen

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-03

Stufe 7a aus RICHTUNG.md:

* `sache` bekommt `abgang` (verkauft, weg), `abgang_am`, `erloes` und
  `abgang_plattform`. Die Zeile bleibt (Owner): sie faellt aus jeder Liste,
  „was hatte ich mal" und die Erloesrechnung bleiben beantwortbar.
* `verbleib` kennt zusaetzlich „vermisst". Das ist nur ein neuer Wert in einer
  Textspalte und braucht keine Schemaaenderung.
"""

from alembic import op
import sqlalchemy as sa


revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sache") as b:
        b.add_column(sa.Column("abgang", sa.String(20), nullable=True))
        b.add_column(sa.Column("abgang_am", sa.Date, nullable=True))
        b.add_column(sa.Column("erloes", sa.Float, nullable=True))
        b.add_column(sa.Column("abgang_plattform", sa.String(60), nullable=True))
        b.create_index("ix_sache_abgang", ["abgang"])


def downgrade() -> None:
    # Vermisst gibt es davor nicht: zurueck auf den Shopfloor, ohne Grund.
    op.get_bind().execute(sa.text(
        "UPDATE sache SET verbleib = 'shopfloor', shopfloor_grund = NULL WHERE verbleib = 'vermisst'"))
    with op.batch_alter_table("sache") as b:
        b.drop_index("ix_sache_abgang")
        for spalte in ("abgang_plattform", "erloes", "abgang_am", "abgang"):
            b.drop_column(spalte)
