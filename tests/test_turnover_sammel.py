"""Sammelabruf der Verbrauchsraten: ein Aufruf statt einem je Produkt.

★ Der Anlass, gemessen am 2026-09-13: mealprep rief ``/api/stats/turnover/{id}``
in einer Schleife, ein Dashboard-Aufruf kostete 17 Anfragen an lager, 14 davon
Turnover. Bei einem Deckel von 60 je Minute reichte das fuer drei Aufrufe.
Danach kam 429, und der Adapter drueben macht aus jedem Fehler eine Null: aus
einer ueberschrittenen Grenze wurde ein plausibel aussehender Messwert.

Diese Tests halten drei Dinge fest, die dabei wichtig sind:

1. Der Sammelabruf braucht **eine** Abfrage, nicht eine je Produkt. Sonst
   verschiebt er das Problem nur von HTTP in die Datenbank.
2. Er liefert **dieselben Zahlen** wie die Einzelauskunft. Zwei Rechenwege fuer
   dieselbe Zahl driften, und der seltener benutzte driftet unbemerkt.
3. Ein Produkt ohne Verbrauch **fehlt** in der Antwort, statt mit Null
   dazustehen. Der Unterschied zwischen "gemessen, keine Bewegung" und "nicht
   gemessen" ist genau der, an dem die Einkaufsliste gescheitert ist.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import ConsumptionEvent, Product, StockEntry
from app.services.stats import StatsService
from tests.test_stats import _QueryCounter


@pytest.fixture
def verbrauchte_produkte(db_session):
    """Drei Produkte, zwei davon mit Verbrauch in den letzten Tagen."""
    produkte = [
        Product(name=f"Zutat {i}", default_unit="g") for i in range(3)
    ]
    db_session.add_all(produkte)
    db_session.flush()

    posten = [
        StockEntry(product_id=p.id, quantity=1000.0, unit="g", location="Lager")
        for p in produkte
    ]
    db_session.add_all(posten)
    db_session.flush()

    jetzt = datetime.now(timezone.utc)
    # Produkt 0: 90 g in Summe, Produkt 1: 30 g. Produkt 2 bleibt unberuehrt.
    db_session.add_all([
        ConsumptionEvent(
            stock_entry_id=posten[0].id,
            amount=60.0,
            unit="g",
            reason="verbraucht",
            consumed_at=jetzt - timedelta(days=2),
        ),
        ConsumptionEvent(
            stock_entry_id=posten[0].id,
            amount=30.0,
            unit="g",
            reason="verbraucht",
            consumed_at=jetzt - timedelta(days=1),
        ),
        ConsumptionEvent(
            stock_entry_id=posten[1].id,
            amount=30.0,
            unit="g",
            reason="verbraucht",
            consumed_at=jetzt - timedelta(days=1),
        ),
    ])
    db_session.commit()
    return produkte


def test_sammelabruf_braucht_eine_abfrage(db_session, verbrauchte_produkte):
    """Der Sinn der Uebung: eine Abfrage, nicht eine je Produkt."""
    stats = StatsService(db_session)
    ids = [p.id for p in verbrauchte_produkte]

    db_session.expire_all()
    with _QueryCounter() as qc:
        ergebnis = stats.turnover_rates(ids)

    assert len(ergebnis) == 2
    assert qc.count == 1, (
        f"turnover_rates() fuehrte {qc.count} SELECTs aus, erwartet 1. "
        f"Sonst ist die HTTP-Schleife nur eine SQL-Schleife geworden. "
        f"Statements: {qc.statements}"
    )


def test_sammel_und_einzeln_liefern_dasselbe(db_session, verbrauchte_produkte):
    """Zwei Wege zur selben Zahl duerfen nicht auseinanderlaufen."""
    stats = StatsService(db_session)
    ids = [p.id for p in verbrauchte_produkte]

    sammel = {zeile["product_id"]: zeile for zeile in stats.turnover_rates(ids)}
    for pid in ids:
        einzeln = stats.turnover_rate(pid)
        if einzeln is None:
            assert pid not in sammel
            continue
        assert sammel[pid] == einzeln


def test_produkt_ohne_verbrauch_fehlt_statt_null(db_session, verbrauchte_produkte):
    """Gemessen und ohne Bewegung ist nicht dasselbe wie nicht gemessen.

    Eine Zeile mit ``avg_daily: 0`` waere hier die gefaehrlichere Antwort: sie
    laesst sich nicht mehr von einem Ausfall unterscheiden, sobald sie einmal
    durch einen Adapter gelaufen ist.
    """
    stats = StatsService(db_session)
    ohne_verbrauch = verbrauchte_produkte[2].id

    ergebnis = stats.turnover_rates([p.id for p in verbrauchte_produkte])

    assert ohne_verbrauch not in {zeile["product_id"] for zeile in ergebnis}


def test_ohne_angabe_alle_mit_verbrauch(db_session, verbrauchte_produkte):
    stats = StatsService(db_session)
    ergebnis = stats.turnover_rates(None)
    assert {zeile["product_id"] for zeile in ergebnis} == {
        verbrauchte_produkte[0].id,
        verbrauchte_produkte[1].id,
    }


def test_leere_liste_ist_nicht_alle(db_session, verbrauchte_produkte):
    """``[]`` heisst "ich frage nach nichts", nicht "gib mir alles".

    Der Unterschied zu ``None`` ist keine Feinheit: wer eine leere Auswahl als
    "alles" liest, holt bei jedem Aufruf den ganzen Bestand.
    """
    stats = StatsService(db_session)
    assert stats.turnover_rates([]) == []


def test_endpunkt_filtert_nach_kommaliste(client, verbrauchte_produkte):
    erstes = verbrauchte_produkte[0].id
    resp = client.get("/api/stats/turnover", params={"product_ids": str(erstes)})
    assert resp.status_code == 200
    daten = resp.json()
    assert [zeile["product_id"] for zeile in daten] == [erstes]
    assert daten[0]["avg_daily"] == pytest.approx(round(90.0 / 90, 2))


def test_endpunkt_ohne_angabe_liefert_alle(client, verbrauchte_produkte):
    resp = client.get("/api/stats/turnover")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_endpunkt_lehnt_unsinn_ab(client, verbrauchte_produkte):
    """Keine stille Nachsicht: eine unlesbare Liste ist ein Fehler.

    Wer nicht-numerische Eintraege ueberspringt, beantwortet eine andere Frage
    als die gestellte, und der Aufrufer merkt es nicht.
    """
    resp = client.get("/api/stats/turnover", params={"product_ids": "1,abc"})
    assert resp.status_code == 422


def test_endpunkt_deckelt_die_menge(client, verbrauchte_produkte):
    zuviel = ",".join(str(i) for i in range(1, 502))
    resp = client.get("/api/stats/turnover", params={"product_ids": zuviel})
    assert resp.status_code == 422


def test_einzelabruf_bleibt_erreichbar(client, verbrauchte_produkte):
    """Der alte Weg bleibt: andere Aufrufer haengen daran."""
    erstes = verbrauchte_produkte[0].id
    resp = client.get(f"/api/stats/turnover/{erstes}")
    assert resp.status_code == 200
    assert resp.json()["product_id"] == erstes
