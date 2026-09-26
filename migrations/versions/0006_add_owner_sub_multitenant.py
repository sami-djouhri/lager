"""multi-tenant: owner_sub auf allen Tabellen + Composite-Uniques

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-04

Additiv + rueckwaertskompatibel: bestehende Zeilen werden via server_default dem
bisherigen Owner zugeordnet. Single-Column-Uniques (name/barcode/serial) werden
zu (owner_sub, ...)-Composites, damit verschiedene Tenants dieselben Werte nutzen
koennen. SQLite kann Constraints nicht in-place aendern → batch_alter_table
(Tabellen-Rebuild).
"""

import os

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

# Owner aller Alt-Daten. Kommt aus der Umgebung (DEFAULT_OWNER_SUB), nicht mehr
# aus dem Quelltext: die Kennung gehoert einem konkreten Menschen, und dieses
# Repo soll veroeffentlicht werden koennen (2026-09-05).
#
# Leer ist unbedenklich. Der Wert dient als server_default beim Hinzufuegen der
# NOT-NULL-Spalte, also der Bestandsuebernahme. Bei einer frischen Installation
# gibt es keinen Bestand, und neue Zeilen stempelt ohnehin das ORM
# (app/tenant.py, before_flush), nicht dieser Vorgabewert.
#
# ⚠️ Wer diese Migration auf einer BESTEHENDEN Datenbank zum ersten Mal faehrt,
# sollte DEFAULT_OWNER_SUB setzen, sonst gehoeren die Alt-Daten niemandem.
OWNER = os.environ.get("DEFAULT_OWNER_SUB", "")

# Reflektierte unbenannte SQLite-UNIQUEs bekommen ueber diese Konvention Namen,
# damit drop_constraint sie treffen kann.
NAMING = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def upgrade() -> None:
    # product: unbenannte UNIQUE(name)/UNIQUE(barcode) → Composite
    with op.batch_alter_table("product", naming_convention=NAMING) as b:
        b.add_column(
            sa.Column("owner_sub", sa.String(128), nullable=False, server_default=OWNER)
        )
        b.drop_constraint("uq_product_name", type_="unique")
        b.drop_constraint("uq_product_barcode", type_="unique")
        b.create_unique_constraint("uq_product_owner_name", ["owner_sub", "name"])
        b.create_unique_constraint("uq_product_owner_barcode", ["owner_sub", "barcode"])
        b.create_index("ix_product_owner_sub", ["owner_sub"])

    # electronic_asset: benannte UNIQUEs → Composite
    with op.batch_alter_table("electronic_asset") as b:
        b.add_column(
            sa.Column("owner_sub", sa.String(128), nullable=False, server_default=OWNER)
        )
        b.drop_constraint("uq_electronic_asset_serial", type_="unique")
        b.drop_constraint("uq_electronic_asset_barcode", type_="unique")
        b.create_unique_constraint(
            "uq_electronic_asset_owner_serial", ["owner_sub", "serial"]
        )
        b.create_unique_constraint(
            "uq_electronic_asset_owner_barcode", ["owner_sub", "barcode"]
        )
        b.create_index("ix_electronic_asset_owner_sub", ["owner_sub"])

    # Kind-Tabellen: nur owner_sub + Index (keine Uniques)
    for tbl in ("stock_entry", "consumption_event"):
        with op.batch_alter_table(tbl) as b:
            b.add_column(
                sa.Column("owner_sub", sa.String(128), nullable=False, server_default=OWNER)
            )
            b.create_index(f"ix_{tbl}_owner_sub", ["owner_sub"])


def downgrade() -> None:
    for tbl in ("consumption_event", "stock_entry"):
        with op.batch_alter_table(tbl) as b:
            b.drop_index(f"ix_{tbl}_owner_sub")
            b.drop_column("owner_sub")

    with op.batch_alter_table("electronic_asset") as b:
        b.drop_constraint("uq_electronic_asset_owner_serial", type_="unique")
        b.drop_constraint("uq_electronic_asset_owner_barcode", type_="unique")
        b.create_unique_constraint("uq_electronic_asset_serial", ["serial"])
        b.create_unique_constraint("uq_electronic_asset_barcode", ["barcode"])
        b.drop_index("ix_electronic_asset_owner_sub")
        b.drop_column("owner_sub")

    with op.batch_alter_table("product", naming_convention=NAMING) as b:
        b.drop_constraint("uq_product_owner_name", type_="unique")
        b.drop_constraint("uq_product_owner_barcode", type_="unique")
        b.create_unique_constraint("uq_product_name", ["name"])
        b.create_unique_constraint("uq_product_barcode", ["barcode"])
        b.drop_index("ix_product_owner_sub")
        b.drop_column("owner_sub")
