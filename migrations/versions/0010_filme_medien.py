"""Filme & Medien: Exemplar-Felder an der Sache, eine Zustandsskala

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-01

Stufe 5a aus RICHTUNG.md:

* `sache` bekommt die Felder eines Exemplars (`titel_id` aus dem medien-Katalog,
  `teil`, `edition`, `medium`, `medientyp`, `titel_huelle`).
* EINE Zustandsskala fuer alle Sachen (Owner): die von medien plus „Neu".
  Die Werte aus Stufe 4 und der Altbestand werden umgeschrieben; was keiner
  Stufe entspricht, wird „Ungeprüft" statt geraten.
"""

from alembic import op
import sqlalchemy as sa


revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

NEU = {
    "neu": "Neu", "wie neu": "Sehr gut", "sehr gut": "Sehr gut", "gut": "Gut",
    "gebraucht": "Gebraucht", "defekt": "Beschädigt", "beschädigt": "Beschädigt",
    "ungeprüft": "Ungeprüft",
}
ALT = {"Neu": "neu", "Sehr gut": "wie neu", "Gut": "gut", "Gebraucht": "gebraucht",
       "Beschädigt": "defekt", "Ungeprüft": "gut"}


def upgrade() -> None:
    with op.batch_alter_table("sache") as b:
        b.add_column(sa.Column("titel_id", sa.Integer, nullable=True))
        b.add_column(sa.Column("teil", sa.String(80), nullable=True))
        b.add_column(sa.Column("edition", sa.String(80), nullable=True))
        b.add_column(sa.Column("medium", sa.String(30), nullable=True))
        b.add_column(sa.Column("medientyp", sa.String(30), nullable=True))
        b.add_column(sa.Column("titel_huelle", sa.String(200), nullable=True))
        b.create_index("ix_sache_titel_id", ["titel_id"])
    bind = op.get_bind()
    for sid, wert in bind.execute(sa.text("SELECT id, condition FROM sache")).all():
        neu = NEU.get((wert or "").strip().lower(), "Ungeprüft")
        if neu != wert:
            bind.execute(sa.text("UPDATE sache SET condition = :w WHERE id = :i"), {"w": neu, "i": sid})


def downgrade() -> None:
    bind = op.get_bind()
    for wert, alt in ALT.items():
        bind.execute(sa.text("UPDATE sache SET condition = :a WHERE condition = :w"), {"a": alt, "w": wert})
    with op.batch_alter_table("sache") as b:
        b.drop_index("ix_sache_titel_id")
        for spalte in ("titel_huelle", "medientyp", "medium", "edition", "teil", "titel_id"):
            b.drop_column(spalte)
