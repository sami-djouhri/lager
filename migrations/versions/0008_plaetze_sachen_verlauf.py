"""Grundmodell: platz, sache (aus electronic_asset), verlauf; Posten am Platz

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-01

Stufe 3 aus RICHTUNG.md („Architektur"):

* jeder freie Ortstext an einem Posten wird ein Raum (je Mandant, Kennung
  `L-001` fortlaufend nach Name), der Posten liegt danach dort; der Text faellt.
* `electronic_asset` geht in `sache` auf, Zeilennummern bleiben. Die
  Homelab-Felder fallen ersatzlos („ganz streichen"). `Homelab` und
  `Elektronik` waren keine Orte: jede Sache steht danach ohne Platz auf dem
  Shopfloor, mit Grund „Im Einsatz", wenn ihr usage_status aktiv war
  (critical, homelab_active, daily_use), sonst „noch nicht eingelagert".
"""

from alembic import op
import sqlalchemy as sa


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

AKTIV = ("critical", "homelab_active", "daily_use")

# Spalten, die electronic_asset und sache gemeinsam haben (alles ausser Ort,
# Nutzungsstufe und Homelab-Feldern).
GEMEINSAM = (
    "id", "owner_sub", "name", "category", "brand", "model", "serial", "barcode",
    "condition", "status", "purchase_date", "purchase_price", "purchase_source",
    "purchase_url", "warranty_end", "estimated_resale_value", "resale_confidence",
    "sell_decision", "sell_reason", "desired_min_profit", "manual_pin",
    "market_value_eur", "market_value_at", "ebay_item_id", "ebay_watch_query",
    "external_refs_json", "notes", "created_at", "updated_at",
)


def _zeit():
    return sa.Column("created_at", sa.DateTime, server_default=sa.func.now())


def upgrade() -> None:
    op.create_table(
        "platz",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("owner_sub", sa.String(128), nullable=False, index=True),
        sa.Column("kennung", sa.String(12), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("art", sa.String(10), nullable=False),
        sa.Column("eltern_id", sa.Integer, sa.ForeignKey("platz.id"), nullable=True, index=True),
        sa.Column("inhalt", sa.Text, nullable=True),
        sa.Column("bereich", sa.String(20), nullable=True, index=True),
        _zeit(),
        sa.UniqueConstraint("owner_sub", "kennung", name="uq_platz_owner_kennung"),
    )
    op.create_table(
        "verlauf",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("owner_sub", sa.String(128), nullable=False, index=True),
        sa.Column("ziel", sa.String(10), nullable=False),
        sa.Column("ziel_id", sa.Integer, nullable=False),
        sa.Column("feld", sa.String(30), nullable=False),
        sa.Column("alt", sa.Text, nullable=True),
        sa.Column("neu", sa.Text, nullable=True),
        sa.Column("am", sa.DateTime, server_default=sa.func.now(), index=True),
    )
    op.create_index("ix_verlauf_ziel", "verlauf", ["ziel", "ziel_id"])

    bind = op.get_bind()

    # --- Altorte werden Raeume ---
    with op.batch_alter_table("stock_entry") as b:
        b.add_column(sa.Column("platz_id", sa.Integer, nullable=True))
        b.create_foreign_key("fk_stock_entry_platz", "platz", ["platz_id"], ["id"])
        b.create_index("ix_stock_entry_platz_id", ["platz_id"])

    orte = bind.execute(sa.text(
        "SELECT DISTINCT owner_sub, TRIM(location) FROM stock_entry "
        "WHERE location IS NOT NULL AND TRIM(location) != '' ORDER BY owner_sub, TRIM(location)"
    )).all()
    zaehler: dict[str, int] = {}
    for owner, ort in orte:
        zaehler[owner] = zaehler.get(owner, 0) + 1
        bind.execute(sa.text(
            "INSERT INTO platz (owner_sub, kennung, name, art) VALUES (:o, :k, :n, 'raum')"
        ), {"o": owner, "k": f"L-{zaehler[owner]:03d}", "n": ort})
    bind.execute(sa.text(
        "UPDATE stock_entry SET platz_id = (SELECT p.id FROM platz p "
        "WHERE p.owner_sub = stock_entry.owner_sub AND p.name = TRIM(stock_entry.location))"
    ))
    with op.batch_alter_table("stock_entry") as b:
        b.drop_column("location")

    # --- electronic_asset geht in sache auf ---
    op.create_table(
        "sache",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("owner_sub", sa.String(128), nullable=False, index=True),
        sa.Column("bereich", sa.String(20), nullable=False, server_default="technik", index=True),
        sa.Column("name", sa.String(200), nullable=False, index=True),
        sa.Column("category", sa.String(100), nullable=True, index=True),
        sa.Column("brand", sa.String(100), nullable=True),
        sa.Column("model", sa.String(150), nullable=True),
        sa.Column("serial", sa.String(150), nullable=True),
        sa.Column("barcode", sa.String(50), nullable=True),
        sa.Column("condition", sa.String(30), index=True),
        sa.Column("status", sa.String(30), index=True),
        sa.Column("platz_id", sa.Integer, sa.ForeignKey("platz.id"), nullable=True, index=True),
        sa.Column("verbleib", sa.String(20), nullable=False, server_default="shopfloor",
                  index=True),
        sa.Column("shopfloor_grund", sa.String(30), nullable=True),
        sa.Column("purchase_date", sa.Date, nullable=True),
        sa.Column("purchase_price", sa.Float, nullable=True),
        sa.Column("purchase_source", sa.String(100), nullable=True),
        sa.Column("purchase_url", sa.Text, nullable=True),
        sa.Column("warranty_end", sa.Date, nullable=True),
        sa.Column("estimated_resale_value", sa.Float, nullable=True),
        sa.Column("resale_confidence", sa.String(30), nullable=True),
        sa.Column("sell_decision", sa.String(30), index=True),
        sa.Column("sell_reason", sa.Text, nullable=True),
        sa.Column("desired_min_profit", sa.Float, nullable=True),
        sa.Column("manual_pin", sa.Integer, index=True),
        sa.Column("market_value_eur", sa.Float, nullable=True),
        sa.Column("market_value_at", sa.DateTime, nullable=True),
        sa.Column("ebay_item_id", sa.String(100), nullable=True, index=True),
        sa.Column("ebay_watch_query", sa.String(250), nullable=True),
        sa.Column("external_refs_json", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("owner_sub", "serial", name="uq_sache_owner_serial"),
        sa.UniqueConstraint("owner_sub", "barcode", name="uq_sache_owner_barcode"),
    )
    spalten = ", ".join(GEMEINSAM)
    aktiv = ", ".join(f"'{a}'" for a in AKTIV)
    bind.execute(sa.text(
        f"INSERT INTO sache ({spalten}, bereich, verbleib, shopfloor_grund) "
        f"SELECT {spalten}, 'technik', 'shopfloor', "
        f"CASE WHEN usage_status IN ({aktiv}) THEN 'im_einsatz' END FROM electronic_asset"
    ))
    # Der Verkaufsschutz hiess bisher „Aktiv in Verwendung: critical".
    bind.execute(sa.text(
        "UPDATE sache SET sell_reason = 'Im Einsatz' "
        "WHERE shopfloor_grund = 'im_einsatz' AND sell_reason LIKE 'Aktiv in Verwendung:%'"
    ))
    op.drop_table("electronic_asset")


def downgrade() -> None:
    bind = op.get_bind()
    op.create_table(
        "electronic_asset",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("owner_sub", sa.String(128), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False, index=True),
        sa.Column("category", sa.String(100), nullable=True, index=True),
        sa.Column("brand", sa.String(100), nullable=True),
        sa.Column("model", sa.String(150), nullable=True),
        sa.Column("serial", sa.String(150), nullable=True),
        sa.Column("barcode", sa.String(50), nullable=True),
        sa.Column("condition", sa.String(30), index=True),
        sa.Column("status", sa.String(30), index=True),
        sa.Column("location", sa.String(80)),
        sa.Column("usage_status", sa.String(30), index=True),
        sa.Column("homelab_role", sa.String(100), nullable=True, index=True),
        sa.Column("host_name", sa.String(100), nullable=True, index=True),
        sa.Column("service_refs_json", sa.Text, nullable=True),
        sa.Column("purchase_date", sa.Date, nullable=True),
        sa.Column("purchase_price", sa.Float, nullable=True),
        sa.Column("purchase_source", sa.String(100), nullable=True),
        sa.Column("purchase_url", sa.Text, nullable=True),
        sa.Column("warranty_end", sa.Date, nullable=True),
        sa.Column("estimated_resale_value", sa.Float, nullable=True),
        sa.Column("resale_confidence", sa.String(30), nullable=True),
        sa.Column("sell_decision", sa.String(30), index=True),
        sa.Column("sell_reason", sa.Text, nullable=True),
        sa.Column("desired_min_profit", sa.Float, nullable=True),
        sa.Column("manual_pin", sa.Integer, index=True),
        sa.Column("market_value_eur", sa.Float, nullable=True),
        sa.Column("market_value_at", sa.DateTime, nullable=True),
        sa.Column("ebay_item_id", sa.String(100), nullable=True, index=True),
        sa.Column("ebay_watch_query", sa.String(250), nullable=True),
        sa.Column("external_refs_json", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("owner_sub", "serial", name="uq_electronic_asset_owner_serial"),
        sa.UniqueConstraint("owner_sub", "barcode", name="uq_electronic_asset_owner_barcode"),
    )
    spalten = ", ".join(GEMEINSAM)
    # Werkstatt-Sachen (ab Stufe 6) hatten im alten Modell keinen Platz.
    bind.execute(sa.text(
        f"INSERT INTO electronic_asset ({spalten}, location, usage_status) "
        f"SELECT {spalten}, COALESCE((SELECT name FROM platz WHERE platz.id = sache.platz_id), "
        f"'Elektronik'), CASE WHEN shopfloor_grund = 'im_einsatz' THEN 'daily_use' "
        f"ELSE 'reserve' END FROM sache WHERE bereich = 'technik'"
    ))
    op.drop_table("sache")

    with op.batch_alter_table("stock_entry") as b:
        b.add_column(sa.Column("location", sa.String(50), server_default="Vorratskammer"))
    bind.execute(sa.text(
        "UPDATE stock_entry SET location = COALESCE((SELECT name FROM platz "
        "WHERE platz.id = stock_entry.platz_id), 'Vorratskammer')"
    ))
    with op.batch_alter_table("stock_entry") as b:
        b.drop_index("ix_stock_entry_platz_id")
        b.drop_constraint("fk_stock_entry_platz", type_="foreignkey")
        b.drop_column("platz_id")

    op.drop_index("ix_verlauf_ziel", table_name="verlauf")
    op.drop_table("verlauf")
    op.drop_table("platz")
