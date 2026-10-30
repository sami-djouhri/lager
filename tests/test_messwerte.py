"""Fachliche Messwerte: der Anker muss auch leer existieren, Namen nie.

Gemessen wird gegen die In-Memory-Engine der Suite, nicht ueber HTTP. Der im
Dienst registrierte Sammler liest ``app.db.engine``, also die echte Datei; ein
Test darueber haenge daran, was dort gerade drinsteht.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from prometheus_client import CollectorRegistry, generate_latest

from app.messwerte import LagerSammler, registriere
from app.models import ConsumptionEvent, ElectronicAsset, Product, StockEntry
from tests.conftest import TEST_ENGINE


def _werte(sammler: LagerSammler) -> dict[str, float]:
    gemessen = {}
    for familie in sammler.collect():
        for probe in familie.samples:
            gemessen[probe.name] = probe.value
    return gemessen


@pytest.fixture
def sammler(db_session):
    # db_session legt die Tabellen an und raeumt sie hinterher wieder ab.
    return LagerSammler(TEST_ENGINE)


def test_anker_existiert_auch_bei_leerem_lager(sammler):
    """Auf eine fehlende Zeitreihe kann keine Regel feuern."""
    werte = _werte(sammler)
    assert werte["lager_messwerte_ok"] == 1
    assert werte["lager_buchungen"] == 0
    assert werte["lager_posten"] == 0
    assert werte["lager_produkte"] == 0


def test_altersmetrik_fehlt_solange_nichts_zu_altern_ist(sammler):
    """0 Sekunden hiesse "gerade gebucht" und waere die Umkehrung der Wahrheit."""
    werte = _werte(sammler)
    assert "lager_letzte_buchung_alter_sekunden" not in werte
    assert "lager_letzter_posten_alter_sekunden" not in werte


def test_altersmetrik_erscheint_mit_der_ersten_buchung(sammler, db_session):
    p = Product(name="Reis", default_unit="g")
    db_session.add(p)
    db_session.flush()
    e = StockEntry(product_id=p.id, quantity=500, unit="g", location="Lager")
    db_session.add(e)
    db_session.flush()
    db_session.add(
        ConsumptionEvent(
            stock_entry_id=e.id,
            amount=100,
            unit="g",
            reason="verbraucht",
            consumed_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
    )
    db_session.commit()

    werte = _werte(sammler)
    assert werte["lager_buchungen"] == 1
    # Rund zehn Tage, mit Luft fuer die Laufzeit des Tests.
    assert 9 * 86400 < werte["lager_letzte_buchung_alter_sekunden"] < 11 * 86400
    assert werte["lager_letzter_posten_alter_sekunden"] >= 0


def test_abgelaufene_und_mhd_lose_posten_werden_getrennt_gezaehlt(sammler, db_session):
    p = Product(name="Nudeln", default_unit="g")
    db_session.add(p)
    db_session.flush()
    db_session.add_all([
        StockEntry(product_id=p.id, quantity=1, unit="g", location="L",
                   mhd=date.today() - timedelta(days=5)),
        StockEntry(product_id=p.id, quantity=1, unit="g", location="L",
                   mhd=date.today() + timedelta(days=5)),
        StockEntry(product_id=p.id, quantity=1, unit="g", location="L", mhd=None),
        # Aufgebraucht: zaehlt in keiner der drei Zahlen mit.
        StockEntry(product_id=p.id, quantity=0, unit="g", location="L",
                   mhd=date.today() - timedelta(days=5)),
    ])
    db_session.commit()

    werte = _werte(sammler)
    assert werte["lager_posten"] == 3
    assert werte["lager_posten_abgelaufen"] == 1
    assert werte["lager_posten_ohne_mhd"] == 1


def test_mindestbestand_wird_gezaehlt(sammler, db_session):
    """Deckt den Befund, dass ohne min_stock die Unterbestands-Pfade leer laufen."""
    db_session.add_all([
        Product(name="Mit", default_unit="g", min_stock=500, min_stock_unit="g"),
        Product(name="Ohne", default_unit="g"),
        Product(name="Null", default_unit="g", min_stock=0),
    ])
    db_session.commit()

    werte = _werte(sammler)
    assert werte["lager_produkte"] == 3
    assert werte["lager_produkte_mit_mindestbestand"] == 1


def test_mandanten_werden_gezaehlt_nicht_benannt(sammler, db_session):
    db_session.add_all([
        Product(name="A", default_unit="g", owner_sub="sub-eins"),
        Product(name="B", default_unit="g", owner_sub="sub-eins"),
        Product(name="C", default_unit="g", owner_sub="sub-zwei"),
    ])
    db_session.commit()

    assert _werte(sammler)["lager_mandanten"] == 2


def test_keine_namen_und_keine_kennungen_in_der_ausgabe(db_session):
    """⚠️ Metriken gehen in eine zweite Datenbank und in Alarmtexte.

    Produktnamen, Kategorien und Mandanten-Kennungen haben dort nichts zu
    suchen. Abgesichert im Test, nicht als Vorsatz in einem Kommentar.
    """
    p = Product(
        name="Geheimes Produkt",
        category="Geheime Kategorie",
        default_unit="g",
        owner_sub="geheime-kennung-123",
    )
    db_session.add(p)
    db_session.flush()
    db_session.add(ElectronicAsset(name="Geheimes Geraet", owner_sub="geheime-kennung-123"))
    db_session.commit()

    registry = CollectorRegistry()
    registriere(registry, TEST_ENGINE)
    ausgabe = generate_latest(registry).decode()

    assert "lager_produkte" in ausgabe
    for verboten in (
        "Geheimes Produkt",
        "Geheime Kategorie",
        "Geheimes Geraet",
        "geheime-kennung-123",
    ):
        assert verboten not in ausgabe


def test_defekte_quelle_meldet_null_statt_metrics_zu_toeten(db_session):
    """Ein werfender Collector nimmt /metrics komplett mit, auch die technischen."""

    class _Kaputt:
        def connect(self):
            raise RuntimeError("Datenbank weg")

    werte = _werte(LagerSammler(_Kaputt()))
    assert werte == {"lager_messwerte_ok": 0}


def test_dienst_liefert_die_fachfamilien_aus(client):
    """Der Sammler muss am laufenden Dienst haengen, nicht nur importierbar sein.

    Ohne diese Zeile waere die ganze Datei gruen und /metrics trotzdem
    unveraendert: ein Sammler, den niemand registriert, sammelt nichts.
    """
    text = client.get("/metrics").text
    assert "lager_messwerte_ok" in text
