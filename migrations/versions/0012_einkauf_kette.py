"""Einkauf kennt die Ladenkette

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-07

Preisvergleich Stufe 1 (Owner 2026-11-07): `einkauf.kette` ist eine der fuenf
Ketten aus `app/ketten.py` oder leer (Sonstiger). Der Altbestand wird nach dem
Namen zugeordnet („automatisch nach Name"): enthaelt `laden` den
Kettennamen, ohne Gross- und Kleinschreibung, gilt die Kette.
"""

from alembic import op
import sqlalchemy as sa


revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

# Bewusst kopiert statt aus app.ketten importiert: eine Migration muss auch
# dann noch genau so laufen, wenn sich die Liste spaeter aendert.
_KETTEN = ("kaufland", "lidl", "netto", "akzenta", "picnic")


def upgrade() -> None:
    with op.batch_alter_table("einkauf") as b:
        b.add_column(sa.Column("kette", sa.String(20), nullable=True))
        b.create_index("ix_einkauf_kette", ["kette"])
    bind = op.get_bind()
    for kette in _KETTEN:
        bind.execute(sa.text(
            "UPDATE einkauf SET kette = :k WHERE kette IS NULL AND lower(laden) LIKE :muster"
        ), {"k": kette, "muster": f"%{kette}%"})


def downgrade() -> None:
    with op.batch_alter_table("einkauf") as b:
        b.drop_index("ix_einkauf_kette")
        b.drop_column("kette")
