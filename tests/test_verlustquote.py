"""Verlustquote je Kategorie: Zaehler und Nenner muessen dasselbe messen.

Diese Datei entstand am 2026-10-24 zu einem Befund, nicht zu einem Wunsch.
``get_category_analytics`` rechnete bis dahin
``abgelaufene Lots / (Verbrauchsmenge + abgelaufene Lots)``: der Zaehler eine
Anzahl, der Nenner eine Mischung aus Anzahl und Menge, die Menge selbst eine
Summe aus Gramm, Millilitern und Stueck, und das Zeitfenster galt nur fuer die
eine Haelfte.

Gemessen am Live-Dienst ergab das 100,0 % Verlust in sechs von sieben
Kategorien, waehrend der Nachbar-Tab derselben Seite "Keine Verschwendung -
weiter so!" anzeigte.

Die ersten vier Tests hier fallen gegen den alten Rechenweg. Das ist ihr
Zweck: sie sind der Beweis, dass die Zahl vorher falsch war, und nicht nur
eine Absicherung des neuen Wegs.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.models import ConsumptionEvent, Product, StockEntry
from app.services.stats import StatsService


def _produkt(db, name: str, kategorie: str, einheit: str = "g") -> Product:
    p = Product(name=name, category=kategorie, default_unit=einheit)
    db.add(p)
    db.flush()
    return p


def _posten(db, produkt: Product, menge: float, einheit: str = "g", mhd=None) -> StockEntry:
    e = StockEntry(
        product_id=produkt.id, quantity=menge, unit=einheit, mhd=mhd, location="Lager"
    )
    db.add(e)
    db.flush()
    return e


def _buchung(db, posten: StockEntry, menge: float, grund: str, vor_tagen: int = 1,
             einheit: str | None = None) -> ConsumptionEvent:
    ev = ConsumptionEvent(
        stock_entry_id=posten.id,
        amount=menge,
        unit=einheit or posten.unit,
        reason=grund,
        consumed_at=datetime.now(timezone.utc) - timedelta(days=vor_tagen),
    )
    db.add(ev)
    db.flush()
    return ev


@pytest.fixture
def dienst(db_session):
    return StatsService(db_session), db_session


def _nach_kategorie(zeilen: list[dict]) -> dict[str, dict]:
    return {z["category"]: z for z in zeilen}


def test_quote_kommt_aus_gebuchten_entsorgungen(dienst):
    """900 g verbraucht, 100 g weggeworfen: das sind 10 Prozent, nicht 100."""
    svc, db = dienst
    p = _produkt(db, "Reis", "Getreide")
    e = _posten(db, p, 1000)
    _buchung(db, e, 900, "verbraucht")
    _buchung(db, e, 100, "weggeworfen")

    zeile = _nach_kategorie(svc.get_category_analytics(days=30))["Getreide"]
    assert zeile["waste_percent"] == 10.0
    assert zeile["waste_unit"] == "g"
    assert zeile["events_total"] == 2
    assert zeile["events_discarded"] == 1


def test_abgelaufen_im_regal_ist_kein_verlust(dienst):
    """Der Kernfall des Befunds: abgelaufen und noch da heisst nicht weggeworfen.

    Alter Rechenweg: 1 abgelaufenes Lot / (0 Verbrauch + 1 Lot) = 100 %.
    Ein MHD ist kein Verfallsdatum, und entsorgt wurde hier nichts.
    """
    svc, db = dienst
    p = _produkt(db, "Nudeln", "Getreide")
    _posten(db, p, 500, mhd=date.today() - timedelta(days=200))

    zeile = _nach_kategorie(svc.get_category_analytics(days=30))["Getreide"]
    assert zeile["waste_percent"] == 0.0
    assert zeile["expired_in_stock"] == 1
    assert zeile["active_items"] == 1
    assert zeile["events_total"] == 0


def test_einheiten_werden_nicht_addiert(dienst):
    """Gramm und Stueck stehen getrennt, auch innerhalb einer Kategorie.

    Alter Rechenweg addierte 100 g und 2 Stueck zu "102" und machte daraus
    eine Prozentzahl.
    """
    svc, db = dienst
    kaese = _produkt(db, "Kaese", "Milchprodukte", "g")
    eier = _produkt(db, "Eier", "Milchprodukte", "piece")
    e_kaese = _posten(db, kaese, 500, "g")
    e_eier = _posten(db, eier, 10, "piece")
    _buchung(db, e_kaese, 400, "verbraucht", einheit="g")
    _buchung(db, e_kaese, 100, "weggeworfen", einheit="g")
    _buchung(db, e_eier, 8, "verbraucht", einheit="piece")

    zeile = _nach_kategorie(svc.get_category_analytics(days=30))["Milchprodukte"]
    je_einheit = {e["unit"]: e for e in zeile["by_unit"]}
    assert je_einheit["g"] == {
        "unit": "g", "consumed": 400.0, "discarded": 100.0, "waste_percent": 20.0
    }
    assert je_einheit["piece"] == {
        "unit": "piece", "consumed": 8.0, "discarded": 0.0, "waste_percent": 0.0
    }
    # Leiteinheit ist die mit der groessten Bewegung: 500 g gegen 8 Stueck.
    assert zeile["waste_unit"] == "g"
    assert zeile["waste_percent"] == 20.0


def test_zeitfenster_gilt_fuer_beide_seiten(dienst):
    """Eine Entsorgung von vor 60 Tagen zaehlt in einem 30-Tage-Fenster nicht.

    Alter Rechenweg: die Abgelaufenen hatten ueberhaupt kein Fenster, ein alter
    Posten wurde also mit jedem Tag schwerer, weil der Verbrauch im Nenner
    wegfiel.
    """
    svc, db = dienst
    p = _produkt(db, "Butter", "Milchprodukte")
    e = _posten(db, p, 250)
    _buchung(db, e, 250, "weggeworfen", vor_tagen=60)

    kurz = _nach_kategorie(svc.get_category_analytics(days=30))["Milchprodukte"]
    assert kurz["events_total"] == 0
    assert kurz["waste_percent"] == 0.0
    assert kurz["waste_unit"] is None

    lang = _nach_kategorie(svc.get_category_analytics(days=90))["Milchprodukte"]
    assert lang["events_discarded"] == 1
    assert lang["waste_percent"] == 100.0


def test_ohne_buchung_gibt_es_keine_leiteinheit(dienst):
    """Null Prozent und "nicht gemessen" duerfen nicht gleich aussehen."""
    svc, db = dienst
    p = _produkt(db, "Salz", "Gewuerze")
    _posten(db, p, 1000)

    zeile = _nach_kategorie(svc.get_category_analytics(days=30))["Gewuerze"]
    assert zeile["waste_unit"] is None
    assert zeile["by_unit"] == []
    assert zeile["waste_percent"] == 0.0


def test_unbekannter_grund_gilt_als_abgang_nicht_als_verlust(dienst):
    """Ein neuer Grund darf nicht stillschweigend zum Verlust werden."""
    svc, db = dienst
    p = _produkt(db, "Mehl", "Getreide")
    e = _posten(db, p, 1000)
    _buchung(db, e, 1000, "verschenkt")

    zeile = _nach_kategorie(svc.get_category_analytics(days=30))["Getreide"]
    assert zeile["events_total"] == 1
    assert zeile["events_discarded"] == 0
    assert zeile["waste_percent"] == 0.0


def test_posten_ohne_kategorie_bekommt_einen_platz(dienst):
    svc, db = dienst
    p = Product(name="Irgendwas", category=None, default_unit="g")
    db.add(p)
    db.flush()
    _posten(db, p, 100)

    namen = {z["category"] for z in svc.get_category_analytics(days=30)}
    assert "Ohne Kategorie" in namen


def test_reihenfolge_ist_bei_gleicher_quote_stabil(dienst):
    """Gleiche Quote, gleiche Zahl Entsorgungen: dann entscheidet der Name.

    Ohne diesen Tiebreak wechselt die Reihenfolge der Kacheln zwischen zwei
    Aufrufen, was wie eine Datenaenderung aussieht.
    """
    svc, db = dienst
    for name, kategorie in (("A-Ware", "Zucker"), ("B-Ware", "Anderes")):
        p = _produkt(db, name, kategorie)
        e = _posten(db, p, 100)
        _buchung(db, e, 50, "verbraucht")
        _buchung(db, e, 50, "weggeworfen")

    reihenfolge = [z["category"] for z in svc.get_category_analytics(days=30)]
    assert reihenfolge == sorted(reihenfolge)
    assert reihenfolge == [z["category"] for z in svc.get_category_analytics(days=30)]


def test_route_liefert_die_neuen_felder(client):
    """Die Antwortform ist Teil des Vertrags: das Frontend liest genau diese Namen."""
    pid = client.post(
        "/api/products", json={"name": "Reis", "default_unit": "g", "category": "Getreide"}
    ).json()["id"]
    client.post("/api/stock", json={"product_id": pid, "quantity": 500, "unit": "g"})

    zeilen = client.get("/api/stats/categories?days=30").json()
    assert zeilen
    assert set(zeilen[0]) == {
        "category",
        "active_items",
        "expired_in_stock",
        "waste_percent",
        "waste_unit",
        "events_total",
        "events_discarded",
        "by_unit",
    }
