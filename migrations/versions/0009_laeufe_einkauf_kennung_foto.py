"""Läufe: Einkauf, Preis am Posten, Stück-Kennung und Foto an der Sache

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-01

Stufe 4 aus RICHTUNG.md („Einbuchen- und Lagern-Lauf"):

* `einkauf`: ein Einbuch-Lauf mit Gesamtbetrag und Laden („Gesamt plus
  Einzelpreis", nichts wird bei Vorräten verteilt).
* `stock_entry` bekommt `preis` (für die ganze eingebuchte Menge),
  `eingangsmenge` (die Menge beim Einbuchen; `quantity` sinkt mit jedem
  Verbrauch, ohne sie ließe sich später kein Preis je Einheit rechnen) und
  `einkauf_id`.
* `sache` bekommt `kennung` (`S-0001`, fortlaufend je Mandant, wie `L-001` an
  den Plätzen), `foto` und `einkauf_id`. Der Bestand wird nach Zeilennummer
  durchgezählt.
* Der eindeutige Strichcode an `sache` fällt. Ein Strichcode nennt die
  Sorte, nicht das Stück: zwei gleiche USB-Sticks aus einem Konvolut hätten
  sonst nicht beide eingebucht werden können. Das Stück erkennt man an der
  Kennung (und an der Seriennummer, die eindeutig bleibt).
"""

from alembic import op
import sqlalchemy as sa


revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "einkauf",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("owner_sub", sa.String(128), nullable=False, index=True),
        sa.Column("bereich", sa.String(20), nullable=False, index=True),
        sa.Column("am", sa.Date, nullable=False, index=True),
        sa.Column("laden", sa.String(100), nullable=True),
        sa.Column("gesamt", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    with op.batch_alter_table("stock_entry") as b:
        b.add_column(sa.Column("preis", sa.Float, nullable=True))
        b.add_column(sa.Column("eingangsmenge", sa.Float, nullable=True))
        b.add_column(sa.Column("einkauf_id", sa.Integer, nullable=True))
        b.create_foreign_key("fk_stock_entry_einkauf", "einkauf", ["einkauf_id"], ["id"])
        b.create_index("ix_stock_entry_einkauf_id", ["einkauf_id"])

    with op.batch_alter_table("sache", recreate="always") as b:
        b.drop_constraint("uq_sache_owner_barcode", type_="unique")
        b.add_column(sa.Column("kennung", sa.String(12), nullable=True))
        b.add_column(sa.Column("foto", sa.String(80), nullable=True))
        b.add_column(sa.Column("einkauf_id", sa.Integer, nullable=True))
        b.create_foreign_key("fk_sache_einkauf", "einkauf", ["einkauf_id"], ["id"])
        b.create_index("ix_sache_einkauf_id", ["einkauf_id"])
        b.create_index("ix_sache_barcode", ["barcode"])

    bind = op.get_bind()
    zaehler: dict[str, int] = {}
    for sid, owner in bind.execute(sa.text("SELECT id, owner_sub FROM sache ORDER BY id")).all():
        zaehler[owner] = zaehler.get(owner, 0) + 1
        bind.execute(sa.text("UPDATE sache SET kennung = :k WHERE id = :i"),
                     {"k": f"S-{zaehler[owner]:04d}", "i": sid})

    with op.batch_alter_table("sache", recreate="always") as b:
        b.alter_column("kennung", existing_type=sa.String(12), nullable=False)
        b.create_unique_constraint("uq_sache_owner_kennung", ["owner_sub", "kennung"])


def downgrade() -> None:
    bind = op.get_bind()
    # Der eindeutige Strichcode kommt zurück. Gibt es inzwischen zwei Sachen
    # mit demselben, behält die älteste ihn; die übrigen verlieren ihn, statt
    # dass das Zurückrollen an der Datenbank scheitert.
    bind.execute(sa.text(
        "UPDATE sache SET barcode = NULL WHERE barcode IS NOT NULL AND id NOT IN ("
        "SELECT MIN(id) FROM sache WHERE barcode IS NOT NULL GROUP BY owner_sub, barcode)"
    ))
    with op.batch_alter_table("sache", recreate="always") as b:
        b.drop_constraint("uq_sache_owner_kennung", type_="unique")
        b.drop_index("ix_sache_barcode")
        b.drop_index("ix_sache_einkauf_id")
        b.drop_constraint("fk_sache_einkauf", type_="foreignkey")
        b.drop_column("einkauf_id")
        b.drop_column("foto")
        b.drop_column("kennung")
        b.create_unique_constraint("uq_sache_owner_barcode", ["owner_sub", "barcode"])

    with op.batch_alter_table("stock_entry") as b:
        b.drop_index("ix_stock_entry_einkauf_id")
        b.drop_constraint("fk_stock_entry_einkauf", type_="foreignkey")
        b.drop_column("einkauf_id")
        b.drop_column("eingangsmenge")
        b.drop_column("preis")

    op.drop_table("einkauf")
