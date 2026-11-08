"""Migration 0009 an einem Bestand im Stand 0008.

Geprueft wird, was nur die Migration kann: jede vorhandene Sache bekommt
ihre Kennung je Mandant nach Zeilennummer, danach duerfen zwei Sachen denselben
Strichcode tragen, und der Rueckweg laesst den Strichcode nur an der aeltesten.
"""

from __future__ import annotations

import sqlite3

from alembic import command

from tests.test_migration_0008 import alembic_cfg  # noqa: F401  (Fixture)


def _sache(c, nr, owner, barcode=None):
    c.execute("INSERT INTO sache (id, owner_sub, bereich, name, condition, status, verbleib, "
              "sell_decision, manual_pin, barcode) VALUES (?, ?, 'technik', ?, 'gut', 'aktiv', "
              "'shopfloor', 'behalten', 0, ?)", (nr, owner, f"Ding {nr}", barcode))


def test_hin_und_zurueck(alembic_cfg):  # noqa: F811
    cfg, db = alembic_cfg
    command.upgrade(cfg, "0008")
    c = sqlite3.connect(db)
    _sache(c, 3, "A", "4006381333627")
    _sache(c, 5, "B")
    _sache(c, 9, "A")
    c.commit()
    c.close()

    command.upgrade(cfg, "head")
    c = sqlite3.connect(db)
    assert c.execute("SELECT id, kennung FROM sache ORDER BY id").fetchall() == [
        (3, "S-0001"), (5, "S-0001"), (9, "S-0002")]
    # Derselbe Strichcode ein zweites Mal: die Sorte, nicht das Stueck.
    c.execute("INSERT INTO sache (id, owner_sub, kennung, bereich, name, condition, status, "
              "verbleib, sell_decision, manual_pin, barcode) VALUES (11, 'A', 'S-0003', "
              "'technik', 'Ding 11', 'gut', 'aktiv', 'shopfloor', 'behalten', 0, '4006381333627')")
    c.execute("INSERT INTO einkauf (owner_sub, bereich, am, gesamt) VALUES ('A', 'technik', "
              "'2026-11-01', 9.5)")
    c.commit()
    cols = {r[1] for r in c.execute("PRAGMA table_info(stock_entry)")}
    assert {"preis", "eingangsmenge", "einkauf_id"} <= cols
    c.close()

    command.downgrade(cfg, "0008")
    c = sqlite3.connect(db)
    assert c.execute("SELECT id, barcode FROM sache ORDER BY id").fetchall() == [
        (3, "4006381333627"), (5, None), (9, None), (11, None)]
    assert "einkauf" not in {r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    c.close()
