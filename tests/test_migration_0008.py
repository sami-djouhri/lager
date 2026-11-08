"""Migration 0008 an einer Datenbank im Stand 0007, wie sie live aussah.

Geprueft wird das, was nur die Migration kann und kein ORM-Test sieht:
Altorte werden Raeume je Mandant, die Posten liegen danach dort, Homelab und
Elektronik werden keine Orte, ein aktiver usage_status wird „Im Einsatz", die
Zeilennummern bleiben, und der Rueckweg stellt den alten Ortstext wieder her.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

WURZEL = Path(__file__).resolve().parent.parent


@pytest.fixture
def alembic_cfg(tmp_path, monkeypatch):
    db = tmp_path / "probe.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db}")
    # Ohne alembic.ini: deren fileConfig baute das Logging um und brach caplog-Tests.
    cfg = Config()
    cfg.set_main_option("script_location", str(WURZEL / "migrations"))
    return cfg, db


def _bestand_0007(db: Path) -> None:
    c = sqlite3.connect(db)
    c.execute("INSERT INTO product (id, owner_sub, name, default_unit, shelf_life_type, bereich) "
              "VALUES (1, 'A', 'Reis', 'g', 'MHD', 'lebensmittel')")
    for owner, ort in (("A", "Kuehlschrank"), ("A", "Vorratskammer"), ("A", "Vorratskammer "),
                       ("B", "Keller")):
        c.execute("INSERT INTO stock_entry (owner_sub, product_id, quantity, unit, location) "
                  "VALUES (?, 1, 5, 'g', ?)", (owner, ort))
    c.execute("INSERT INTO consumption_event (owner_sub, stock_entry_id, amount, unit, reason, "
              "source) VALUES ('A', 1, 1, 'g', 'verbraucht', 'manual')")
    for nr, (ort, stufe, grund) in enumerate((
        ("Homelab", "critical", "Aktiv in Verwendung: critical"),
        ("Elektronik", "reserve", None),
    ), start=7):
        c.execute(
            "INSERT INTO electronic_asset (id, owner_sub, name, condition, status, location, "
            "usage_status, sell_decision, sell_reason, manual_pin, host_name, serial) "
            "VALUES (?, 'A', ?, 'gut', 'aktiv', ?, ?, 'behalten', ?, 0, 'host', ?)",
            (nr, f"Geraet {nr}", ort, stufe, grund, f"S{nr}"),
        )
    c.commit()
    c.close()


def test_hin_und_zurueck(alembic_cfg):
    cfg, db = alembic_cfg
    command.upgrade(cfg, "0007")
    _bestand_0007(db)

    command.upgrade(cfg, "head")
    c = sqlite3.connect(db)
    plaetze = c.execute("SELECT owner_sub, kennung, name, art FROM platz ORDER BY id").fetchall()
    # Je Mandant ab L-001, nach Name; der Leerraum am Ende macht keinen zweiten Raum.
    assert plaetze == [
        ("A", "L-001", "Kuehlschrank", "raum"),
        ("A", "L-002", "Vorratskammer", "raum"),
        ("B", "L-001", "Keller", "raum"),
    ]
    posten = c.execute(
        "SELECT s.owner_sub, p.owner_sub, p.name FROM stock_entry s "
        "JOIN platz p ON p.id = s.platz_id ORDER BY s.id"
    ).fetchall()
    assert len(posten) == 4
    assert all(a == b for a, b, _ in posten), "Posten liegt im Raum eines fremden Mandanten"
    sachen = c.execute(
        "SELECT id, platz_id, verbleib, shopfloor_grund, sell_reason, serial FROM sache ORDER BY id"
    ).fetchall()
    assert sachen == [
        (7, None, "shopfloor", "im_einsatz", "Im Einsatz", "S7"),
        (8, None, "shopfloor", None, None, "S8"),
    ]
    spalten = {r[1] for r in c.execute("PRAGMA table_info(sache)")}
    assert not spalten & {"host_name", "homelab_role", "service_refs_json", "location"}
    assert "location" not in {r[1] for r in c.execute("PRAGMA table_info(stock_entry)")}
    assert c.execute("PRAGMA foreign_key_check").fetchall() == []
    assert c.execute("SELECT COUNT(*) FROM consumption_event").fetchone() == (1,)
    c.close()

    command.downgrade(cfg, "0007")
    c = sqlite3.connect(db)
    orte = [r[0] for r in c.execute("SELECT location FROM stock_entry ORDER BY id")]
    assert orte == ["Kuehlschrank", "Vorratskammer", "Vorratskammer", "Keller"]
    alt = c.execute("SELECT id, location, usage_status FROM electronic_asset ORDER BY id").fetchall()
    assert alt == [(7, "Elektronik", "daily_use"), (8, "Elektronik", "reserve")]
    c.close()

    command.upgrade(cfg, "head")
