"""Stufe 7a: Vermisst, Abgang (Verkauft, Weg) und das Abholen aus medien.

Die Zeile bleibt (Owner, RICHTUNG.md): ein Abgang faellt aus jeder Liste,
„was hatte ich mal" bleibt beantwortbar. Geprueft wird deshalb vor allem, dass
die Sache aus allen Listen verschwindet und aus der Gegenliste nicht.
"""

from __future__ import annotations

from datetime import date

from app.services import medien
from tests.test_filme_medien import EAN, katalog  # noqa: F401 - Fixture


def _platz(client, name="Keller"):
    r = client.post("/api/plaetze", json={"name": name, "art": "raum"})
    assert r.status_code == 201, r.text
    return r.json()


def _sache(client, name="Akkuschrauber", **mehr):
    r = client.post("/api/electronics", json={"name": name, **mehr})
    assert r.status_code == 201, r.text
    return r.json()


def _technik(client, **params):
    return client.get("/api/electronics", params=params).json()["items"]


def _satz(client, schluessel):
    b = next(b for b in client.get("/api/bereiche").json() if b["schluessel"] == schluessel)
    return b["satz"]


def test_verkauft_faellt_aus_jeder_liste_und_steht_in_der_gegenliste(client):
    keller = _platz(client)
    s = _sache(client, platz_id=keller["id"], purchase_price=40)
    r = client.post(f"/api/electronics/{s['id']}/abgang",
                    json={"abgang": "verkauft", "erloes": 55, "plattform": "Kleinanzeigen",
                          "am": "2026-11-02"})
    assert r.status_code == 200, r.text
    a = r.json()
    assert (a["abgang"], a["erloes"], a["abgang_plattform"], a["abgang_am"]) == \
        ("verkauft", 55, "Kleinanzeigen", "2026-11-02")
    assert _technik(client) == []
    assert [x["kennung"] for x in _technik(client, abgegangen=True)] == [s["kennung"]]
    assert client.get(f"/api/plaetze/{keller['id']}").json()["dinge"] == []
    assert client.get("/api/shopfloor").json()["anzahl"] == 0
    assert client.get("/api/suche", params={"q": "akku"}).json()["dinge"] == []
    assert client.get("/api/electronics/portfolio").json()["total_assets"] == 0
    assert _satz(client, "technik")["schluessel"] == "leer"
    # Der Platz ist damit leer und laesst sich loeschen.
    assert client.delete(f"/api/plaetze/{keller['id']}").status_code == 204


def test_ohne_datum_gilt_heute_und_weg_hat_keinen_erloes(client):
    s = _sache(client)
    r = client.post(f"/api/electronics/{s['id']}/abgang", json={"abgang": "weg", "erloes": 3})
    assert r.status_code == 422
    r = client.post(f"/api/electronics/{s['id']}/abgang", json={"abgang": "weg"})
    assert r.json()["abgang_am"] == date.today().isoformat()
    # Zweimal abgehen geht nicht.
    assert client.post(f"/api/electronics/{s['id']}/abgang", json={"abgang": "weg"}).status_code == 422


def test_unbekannter_abgang_wird_abgelehnt(client):
    s = _sache(client)
    r = client.post(f"/api/electronics/{s['id']}/abgang", json={"abgang": "verschenkt"})
    assert r.status_code == 422


def test_zuruecknehmen_stellt_den_stand_vorher_her(client):
    keller = _platz(client)
    s = _sache(client, platz_id=keller["id"])
    assert s["verbleib"] == "eingelagert"
    client.post(f"/api/electronics/{s['id']}/abgang", json={"abgang": "weg"})
    r = client.delete(f"/api/electronics/{s['id']}/abgang")
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["abgang"] is None and a["verbleib"] == "eingelagert" and a["platz_id"] == keller["id"]
    assert [x["id"] for x in _technik(client)] == [s["id"]]
    assert client.delete(f"/api/electronics/{s['id']}/abgang").status_code == 422


def test_abgegangene_sache_laesst_sich_nicht_bearbeiten(client):
    s = _sache(client)
    client.post(f"/api/electronics/{s['id']}/abgang", json={"abgang": "weg"})
    r = client.put(f"/api/electronics/{s['id']}", json={"verbleib": "shopfloor"})
    assert r.status_code == 422


def test_platz_loeschen_nimmt_abgegangenen_den_platz(client):
    keller = _platz(client)
    s = _sache(client, platz_id=keller["id"])
    client.post(f"/api/electronics/{s['id']}/abgang", json={"abgang": "weg"})
    client.delete(f"/api/plaetze/{keller['id']}")
    a = client.delete(f"/api/electronics/{s['id']}/abgang").json()
    # Der Platz ist weg: zurueck auf den Shopfloor statt „eingelagert" ohne Platz.
    assert a["platz_id"] is None and a["verbleib"] == "shopfloor"


def test_etikett_einer_abgegangenen_sache_bucht_nichts(client):
    keller = _platz(client)
    s = _sache(client, serial="SN-1")
    client.post(f"/api/electronics/{s['id']}/abgang", json={"abgang": "verkauft"})
    for code in (s["kennung"], "SN-1"):
        r = client.post("/api/laeufe/lagern",
                        json={"richtung": "ein", "code": code, "platz_id": keller["id"]})
        assert r.status_code == 422 and "verkauft" in r.text, r.text
        r = client.post("/api/laeufe/einbuchen", json={"bereich": "technik", "code": code})
        assert r.status_code == 422 and "verkauft" in r.text, r.text


def test_vermisst_steht_auf_der_startseite_vorn_und_einlagern_findet_es(client):
    keller = _platz(client)
    s = _sache(client, platz_id=keller["id"])
    r = client.put(f"/api/electronics/{s['id']}", json={"verbleib": "vermisst"})
    assert r.status_code == 200, r.text
    assert r.json()["verbleib"] == "vermisst" and r.json()["platz_id"] == keller["id"]
    satz = _satz(client, "technik")
    assert satz["schluessel"] == "vermisst" and satz["blockiert"] is True
    # Nicht auf dem Shopfloor und nicht im Fach, aber in der Liste des Bereichs.
    assert client.get("/api/shopfloor").json()["anzahl"] == 0
    assert [d["verbleib"] for d in client.get(f"/api/plaetze/{keller['id']}").json()["dinge"]] == ["vermisst"]
    assert len(_technik(client)) == 1
    # Gefunden: der Lagern-Lauf legt es zurueck.
    r = client.post("/api/laeufe/lagern",
                    json={"richtung": "ein", "code": s["kennung"], "platz_id": keller["id"]})
    assert r.json()["art"] == "gebucht", r.text
    assert _satz(client, "technik")["schluessel"] != "vermisst"


def test_vermisst_mit_grund_verliert_den_grund(client):
    s = _sache(client, shopfloor_grund="reparatur")
    r = client.put(f"/api/electronics/{s['id']}", json={"verbleib": "vermisst"})
    assert r.json()["shopfloor_grund"] is None


# ---------------------------------------------------------------------------
# Filme & Medien: der Abgang kommt aus medien
# ---------------------------------------------------------------------------

def _film(client, **mehr):
    r = client.post("/api/laeufe/einbuchen", json={
        "bereich": "medien", "code": EAN, "titel_id": 7, "name": "Two and a Half Men",
        "medium": "DVD", "bestaetigt": True, **mehr})
    assert r.status_code == 200, r.text
    return r.json()["sache"]


def test_film_geht_nur_in_medien_ab(client, katalog):  # noqa: F811
    f = _film(client)
    r = client.post(f"/api/electronics/{f['id']}/abgang", json={"abgang": "verkauft"})
    assert r.status_code == 422 and "medien" in r.text


def test_abgang_aus_medien_wird_abgeholt_und_fehlt_im_abzug(client, katalog, db_session):  # noqa: F811
    f = _film(client)
    g = _film(client)
    katalog.abgaenge = [
        {"kennung": f["kennung"], "abgang": "Verkauft", "am": "2026-11-02", "erloes": 4.5,
         "plattform": "momox"},
        # Unbekannte Kennung und unbekannter Wert: uebersprungen, nicht geraten.
        {"kennung": "S-0999", "abgang": "Verkauft", "am": None, "erloes": None, "plattform": None},
        {"kennung": g["kennung"], "abgang": "Verliehen", "am": None, "erloes": None, "plattform": None},
    ]
    assert medien.abgaenge_abholen(db_session) == 1
    db_session.expire_all()
    weg = _technik(client, bereich="medien", abgegangen=True)
    assert [(x["kennung"], x["abgang"], x["erloes"], x["abgang_plattform"], x["abgang_am"])
            for x in weg] == [(f["kennung"], "verkauft", 4.5, "momox", "2026-11-02")]
    assert [s["kennung"] for s in medien.abzug(db_session)] == [g["kennung"]]
    # Zweites Abholen derselben Liste bucht nichts doppelt.
    assert medien.abgaenge_abholen(db_session) == 0
    # Zuruecknehmen nur in medien, sonst holte der naechste Abgleich ihn wieder.
    assert client.delete(f"/api/electronics/{f['id']}/abgang").status_code == 422


# ---------------------------------------------------------------------------
# Ausbuch-Vorschlag fuer lange Vermisstes (aus dem Verlauf)
# ---------------------------------------------------------------------------

def _vor_tagen(db_session, sache_id, tage):
    """Den juengsten Vermisst-Eintrag zurueckdatieren (der Verlauf ist die Uhr)."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    from app.models import Verlauf

    v = db_session.execute(select(Verlauf).where(
        Verlauf.ziel == "sache", Verlauf.ziel_id == sache_id, Verlauf.feld == "verbleib",
        Verlauf.neu == "vermisst").order_by(Verlauf.id.desc())).scalars().first()
    v.am = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=tage)
    db_session.commit()


def test_nach_30_tagen_vermisst_schlaegt_das_lager_ausbuchen_vor(client, db_session):
    s = _sache(client)
    client.put(f"/api/electronics/{s['id']}", json={"verbleib": "vermisst"})
    a = _technik(client)[0]
    assert a["vermisst_seit"] is not None and a["ausbuchen_vorschlagen"] is False
    assert _satz(client, "technik")["schluessel"] == "vermisst"
    _vor_tagen(db_session, s["id"], 31)
    assert _technik(client)[0]["ausbuchen_vorschlagen"] is True
    satz = _satz(client, "technik")
    assert satz["schluessel"] == "vermisst_lange" and satz["blockiert"] is True
    # Nur ein Vorschlag: gebucht ist nichts.
    assert _technik(client)[0]["abgang"] is None


def test_wieder_vermisst_altert_ab_dem_letzten_mal(client, db_session):
    keller = _platz(client)
    s = _sache(client, platz_id=keller["id"])
    client.put(f"/api/electronics/{s['id']}", json={"verbleib": "vermisst"})
    _vor_tagen(db_session, s["id"], 60)
    client.put(f"/api/electronics/{s['id']}", json={"verbleib": "eingelagert"})
    client.put(f"/api/electronics/{s['id']}", json={"verbleib": "vermisst"})
    # Der erste Eintrag ist 60 Tage alt, der laufende von heute.
    assert _technik(client)[0]["ausbuchen_vorschlagen"] is False
    assert _satz(client, "technik")["schluessel"] == "vermisst"
