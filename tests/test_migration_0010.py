"""Migration 0010: eine Zustandsskala, Exemplar-Felder an der Sache."""

from __future__ import annotations

import sqlite3

from alembic import command

from tests.test_migration_0008 import alembic_cfg  # noqa: F401  (Fixture)


def test_zustaende_werden_umgeschrieben(alembic_cfg):  # noqa: F811
    cfg, db = alembic_cfg
    command.upgrade(cfg, "0009")
    c = sqlite3.connect(db)
    for nr, zustand in enumerate(("gut", "defekt", "wie neu", "irgendwas", "neu"), start=1):
        c.execute("INSERT INTO sache (id, owner_sub, kennung, bereich, name, condition, status, "
                  "verbleib, sell_decision, manual_pin) VALUES (?, 'A', ?, 'technik', 'x', ?, "
                  "'aktiv', 'shopfloor', 'behalten', 0)", (nr, f"S-{nr:04d}", zustand))
    c.commit()
    c.close()

    command.upgrade(cfg, "head")
    c = sqlite3.connect(db)
    # Was keiner Stufe entspricht, wird „Ungeprüft" statt geraten.
    assert [r[0] for r in c.execute("SELECT condition FROM sache ORDER BY id")] == [
        "Gut", "Beschädigt", "Sehr gut", "Ungeprüft", "Neu"]
    spalten = {r[1] for r in c.execute("PRAGMA table_info(sache)")}
    assert {"titel_id", "teil", "edition", "medium", "medientyp", "titel_huelle"} <= spalten
    c.close()

    command.downgrade(cfg, "0009")
    c = sqlite3.connect(db)
    assert [r[0] for r in c.execute("SELECT condition FROM sache ORDER BY id")] == [
        "gut", "defekt", "wie neu", "gut", "neu"]
    c.close()
