"""Einbuchen- und Lagern-Lauf, Einkauf, Fotos (Stufe 4, RICHTUNG.md).

Jeder Test haelt einen Entscheid vom 2026-11-01 fest, nicht eine
Implementierung: ein Posten je MHD, Gesamt plus Einzelpreis ohne Verteilung bei
Vorraeten, Verteilung bei Sachen, drei Richtungen im Lagern-Lauf, MHD- und
Zustands-Rueckfrage nur bei echtem Unterschied, Etikett schlaegt Strichcode.
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest

EAN = "4006381333627"
EAN2 = "4000521003753"


@pytest.fixture(autouse=True)
def _kein_openfoodfacts():
    # Kein Testlauf fragt einen fremden Dienst.
    with patch("app.api.routes_laeufe.BarcodeService.lookup", new=AsyncMock(return_value=None)):
        yield


@pytest.fixture
def foto_ablage(tmp_path, monkeypatch):
    monkeypatch.setenv("LAGER_FOTO_DIR", str(tmp_path / "fotos"))
    return tmp_path / "fotos"


def _platz(client, name, art="raum", eltern=None):
    r = client.post("/api/plaetze", json={"name": name, "art": art, "eltern_id": eltern})
    assert r.status_code == 201, r.text
    return r.json()


def _ein(client, **body):
    body.setdefault("bereich", "lebensmittel")
    r = client.post("/api/laeufe/einbuchen", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _lagern(client, **body):
    r = client.post("/api/laeufe/lagern", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _produkt(client, **mehr):
    body = {"name": "Joghurt", "barcode": EAN, "default_unit": "piece", **mehr}
    r = client.post("/api/products", json=body)
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Einbuchen: Vorrat
# ---------------------------------------------------------------------------

def test_unbekannter_strichcode_fragt_nach_dem_namen_und_legt_dann_an(client):
    erg = _ein(client, code=EAN)
    assert erg["art"] == "name_fehlt"
    erg = _ein(client, code=EAN, name="Haferdrink", kategorie="Getreide")
    assert erg["art"] == "neu" and erg["produkt_neu"] is True
    assert erg["posten"]["product_name"] == "Haferdrink"
    assert erg["posten"]["quantity"] == 1 and erg["posten"]["unit"] == "piece"
    # Ab jetzt kennt der Scan das Produkt.
    assert _ein(client, code=EAN)["art"] == "neu"


def test_vorschlag_kommt_aus_openfoodfacts(client):
    treffer = {"barcode": EAN, "name": "Hafer Drink", "category": "Pflanzendrinks"}
    with patch("app.api.routes_laeufe.BarcodeService.lookup", new=AsyncMock(return_value=treffer)):
        erg = _ein(client, code=EAN)
    assert erg["art"] == "name_fehlt"
    assert erg["vorschlag"] == {"name": "Hafer Drink", "category": "Pflanzendrinks",
                                "quelle": "OpenFoodFacts"}


def test_ein_posten_je_mhd(client):
    """Owner: drei gleiche Dosen im selben Lauf sind ein Posten, solange das MHD gleich ist."""
    _produkt(client, typical_pack_sizes=[1], shelf_life_days_default=10)
    a = _ein(client, code=EAN)
    b = _ein(client, code=EAN, lauf_posten=[a["posten"]["id"]])
    assert b["art"] == "mehr" and b["posten"]["id"] == a["posten"]["id"]
    assert b["posten"]["quantity"] == 2 and b["posten"]["eingangsmenge"] == 2
    # Das MHD am ersten Posten korrigiert: der naechste Scan ist ein neuer Posten.
    client.put(f"/api/stock/{a['posten']['id']}",
               json={"mhd": (date.today() + timedelta(days=3)).isoformat()})
    c = _ein(client, code=EAN, lauf_posten=[a["posten"]["id"]])
    assert c["art"] == "neu" and c["posten"]["id"] != a["posten"]["id"]
    # Ohne Lauf-Zusammenhang wird nie zusammengelegt.
    assert _ein(client, code=EAN)["art"] == "neu"


def test_mhd_kommt_als_vorschlag_aus_der_haltbarkeit(client):
    _produkt(client, shelf_life_days_default=14)
    erg = _ein(client, code=EAN)
    assert erg["posten"]["mhd"] == (date.today() + timedelta(days=14)).isoformat()


def test_produkt_in_gramm_ohne_anhaltspunkt_fragt_nach_der_menge(client):
    """Kein „1 g Mehl": eine erfundene Menge saehe aus wie eine Buchung."""
    _produkt(client, name="Mehl", default_unit="g")
    erg = _ein(client, code=EAN)
    assert erg["art"] == "menge_fehlt" and erg["produkt_name"] == "Mehl"
    erg = _ein(client, code=EAN, menge=1, einheit="kg")
    assert erg["posten"]["quantity"] == 1000 and erg["posten"]["unit"] == "g"
    # Danach nimmt der Lauf die Menge des letzten Postens.
    assert _ein(client, code=EAN)["posten"]["quantity"] == 1000


def test_platz_als_vorgabe(client):
    kuehl = _platz(client, "Kühlschrank")
    _produkt(client)
    erg = _ein(client, code=EAN, platz_id=kuehl["id"])
    assert erg["posten"]["platz_id"] == kuehl["id"]


def test_etiketten_werden_nie_zu_produkten(client):
    r = client.post("/api/laeufe/einbuchen", json={"bereich": "lebensmittel", "code": "L-001"})
    assert r.status_code == 422
    r = client.post("/api/laeufe/einbuchen", json={"bereich": "lebensmittel", "code": "S-0001"})
    assert r.status_code == 422


def test_kein_lauf_in_kistenbereichen(client):
    r = client.post("/api/laeufe/einbuchen", json={"bereich": "kleidung", "name": "Pulli"})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Einbuchen: Sachen
# ---------------------------------------------------------------------------

def test_sache_bekommt_kennung_und_landet_ohne_grund_auf_dem_shopfloor(client):
    erg = _ein(client, bereich="technik", code=EAN, name="USB-Stick", zustand="Neu")
    s = erg["sache"]
    assert erg["art"] == "neu" and s["kennung"] == "S-0001"
    assert s["verbleib"] == "shopfloor" and s["shopfloor_grund"] is None
    assert s["condition"] == "Neu" and s["barcode"] == EAN


def test_zwei_gleiche_sachen_aus_einem_konvolut(client):
    """Der Strichcode nennt die Sorte: das zweite Stueck darf nicht an der Datenbank scheitern."""
    _ein(client, bereich="technik", code=EAN, name="USB-Stick")
    erg = _ein(client, bereich="technik", code=EAN)
    assert erg["art"] == "bekannt" and len(erg["vorhanden"]) == 1
    erg = _ein(client, bereich="technik", code=EAN, bestaetigt=True)
    assert erg["art"] == "neu" and erg["sache"]["name"] == "USB-Stick"
    assert erg["sache"]["kennung"] == "S-0002"


def test_eigenes_etikett_ist_kein_zugang(client):
    _ein(client, bereich="technik", name="Bohrmaschine")
    erg = _ein(client, bereich="technik", code="S-1")
    assert erg["art"] == "wiedergesehen" and erg["sache"]["kennung"] == "S-0001"
    assert client.get("/api/electronics").json()["total"] == 1


def test_seriennummer_meint_ein_geraet(client):
    _ein(client, bereich="technik", code="SN-AB12", name="Router")
    assert _ein(client, bereich="technik", code="SN-AB12")["art"] == "wiedergesehen"


def test_kennung_wird_nach_dem_loeschen_nicht_neu_vergeben(client):
    a = _ein(client, bereich="technik", name="A")["sache"]
    client.delete(f"/api/electronics/{a['id']}")
    assert _ein(client, bereich="technik", name="B")["sache"]["kennung"] == "S-0002"


# ---------------------------------------------------------------------------
# Abschluss: Einkauf
# ---------------------------------------------------------------------------

def test_vorrat_gesamtpreis_wird_nicht_verteilt(client):
    _produkt(client)
    a = _ein(client, code=EAN, preis=1.29)["posten"]
    b = _ein(client, name="Brot")["posten"]
    r = client.post("/api/laeufe/abschluss", json={
        "bereich": "lebensmittel", "posten": [a["id"], b["id"]], "gesamt": 47.80, "laden": "Kaufland"})
    assert r.status_code == 200, r.text
    e = r.json()
    assert e["gesamt"] == 47.80 and e["laden"] == "Kaufland"
    assert e["posten"] == 2 and e["einzelpreise"] == 1.29 and e["ohne_preis"] == 1
    assert e["verteilt"] == {}
    # Brot bleibt ohne Preis: ein verteilter waere ausgedacht.
    assert client.get(f"/api/stock/{b['id']}").json()["preis"] is None
    assert client.get(f"/api/stock/{a['id']}").json()["einkauf_id"] == e["id"]


def test_sachen_bekommen_den_rest_verteilt(client):
    ids = [_ein(client, bereich="technik", name=f"Teil {i}", preis=10 if i == 0 else None)["sache"]["id"]
           for i in range(4)]
    e = client.post("/api/laeufe/abschluss", json={
        "bereich": "technik", "sachen": ids, "gesamt": 40}).json()
    # 40 minus 10 Einzelpreis, 30 auf drei Stuecke.
    assert sorted(e["verteilt"].values()) == [10.0, 10.0, 10.0]
    assert e["ohne_preis"] == 0


def test_verteilung_ist_auf_den_cent_genau(client):
    ids = [_ein(client, bereich="technik", name=f"Teil {i}")["sache"]["id"] for i in range(3)]
    e = client.post("/api/laeufe/abschluss", json={"bereich": "technik", "sachen": ids,
                                                   "gesamt": 10}).json()
    assert round(sum(e["verteilt"].values()), 2) == 10.0


def test_einzelpreise_ueber_dem_gesamtbetrag(client):
    a = _ein(client, bereich="technik", name="A", preis=30)["sache"]["id"]
    b = _ein(client, bereich="technik", name="B")["sache"]["id"]
    r = client.post("/api/laeufe/abschluss", json={"bereich": "technik", "sachen": [a, b],
                                                   "gesamt": 20})
    assert r.status_code == 422


def test_ohne_betrag_und_laden_kein_einkauf(client):
    _produkt(client)
    a = _ein(client, code=EAN)["posten"]["id"]
    r = client.post("/api/laeufe/abschluss", json={"bereich": "lebensmittel", "posten": [a]})
    assert r.status_code == 200 and r.json() is None
    assert client.get("/api/einkaeufe").json() == []


def test_doppelter_abschluss_wird_abgewiesen(client):
    _produkt(client)
    a = _ein(client, code=EAN)["posten"]["id"]
    body = {"bereich": "lebensmittel", "posten": [a], "gesamt": 5}
    assert client.post("/api/laeufe/abschluss", json=body).status_code == 200
    assert client.post("/api/laeufe/abschluss", json=body).status_code == 422


# ---------------------------------------------------------------------------
# Lagern
# ---------------------------------------------------------------------------

def test_platz_scan_nennt_das_ziel(client):
    keller = _platz(client, "Keller")
    erg = _lagern(client, richtung="ein", code="l-1")
    assert erg["art"] == "platz" and erg["platz"]["id"] == keller["id"]


def test_einlagern_braucht_ein_ziel(client):
    _produkt(client)
    _ein(client, code=EAN)
    r = client.post("/api/laeufe/lagern", json={"richtung": "ein", "code": EAN})
    assert r.status_code == 422


def test_posten_einlagern_umlagern_rausholen(client):
    keller = _platz(client, "Keller")
    kueche = _platz(client, "Küche")
    _produkt(client)
    p = _ein(client, code=EAN, menge=3)["posten"]
    erg = _lagern(client, richtung="ein", code=EAN, platz_id=keller["id"])
    assert erg["art"] == "gebucht" and erg["ding"]["platz_id"] == keller["id"]
    # Der ganze Posten zieht mit einem Scan (Owner).
    assert client.get(f"/api/stock/{p['id']}").json()["quantity"] == 3

    # Einlagern nimmt nur Offenes; Umziehen ist eine eigene Richtung (Owner).
    erg = _lagern(client, richtung="ein", code=EAN, platz_id=kueche["id"])
    assert erg["art"] == "passt_nicht" and "Umlagern" in erg["hinweis"]
    erg = _lagern(client, richtung="um", code=EAN, platz_id=kueche["id"])
    assert erg["art"] == "gebucht" and erg["vorher_pfad"] == "Keller"
    assert erg["ding"]["platz_id"] == kueche["id"]

    # Auch Vorraete kann man aus dem Fach holen (Owner).
    erg = _lagern(client, richtung="aus", code=EAN)
    assert erg["art"] == "gebucht" and erg["ding"]["platz_id"] is None


def test_mhd_rueckfrage_nur_bei_verschiedenen_mhds(client):
    keller = _platz(client, "Keller")
    _produkt(client)
    bald = (date.today() + timedelta(days=4)).isoformat()
    spaet = (date.today() + timedelta(days=11)).isoformat()
    _ein(client, code=EAN, mhd=bald)
    p2 = _ein(client, code=EAN, mhd=spaet)["posten"]
    erg = _lagern(client, richtung="ein", code=EAN, platz_id=keller["id"])
    assert erg["art"] == "welches" and erg["mhds"] == [bald, spaet]
    erg = _lagern(client, richtung="ein", code=EAN, platz_id=keller["id"], mhd=spaet)
    assert erg["ding"]["id"] == p2["id"]
    # Nur noch einer offen: keine Frage mehr.
    assert _lagern(client, richtung="ein", code=EAN, platz_id=keller["id"])["art"] == "gebucht"


def test_sache_rausholen_braucht_einen_grund_und_behaelt_den_platz(client):
    keller = _platz(client, "Keller")
    s = _ein(client, bereich="technik", code=EAN, name="Akkuschrauber")["sache"]
    assert _lagern(client, richtung="ein", code=EAN, platz_id=keller["id"])["art"] == "gebucht"
    erg = _lagern(client, richtung="aus", code="S-0001")
    # Ohne Grund fragt der Lauf nach einem aus dem Bereich des Stuecks.
    assert erg["art"] == "grund_fehlt" and erg["gruende"] == ["im_einsatz", "reparatur", "verkauf_vorbereiten"]
    erg = _lagern(client, richtung="aus", code="S-0001", grund="reparatur")
    assert erg["art"] == "gebucht" and erg["ding"]["shopfloor_grund"] == "reparatur"
    a = client.get(f"/api/electronics/{s['id']}").json()
    # Der Platz bleibt stehen: so findet das Zuruecklegen sein Fach wieder.
    assert a["platz_id"] == keller["id"] and a["verbleib"] == "shopfloor"


def test_zustand_entscheidet_bei_doppelten_sachen(client):
    keller = _platz(client, "Keller")
    _ein(client, bereich="technik", code=EAN, name="Stick", zustand="Neu")
    zwei = _ein(client, bereich="technik", code=EAN, bestaetigt=True, zustand="Beschädigt")["sache"]
    erg = _lagern(client, richtung="ein", code=EAN, platz_id=keller["id"])
    assert erg["art"] == "welches" and erg["zustaende"] == ["Beschädigt", "Neu"]
    erg = _lagern(client, richtung="ein", code=EAN, platz_id=keller["id"], zustand="Beschädigt")
    assert erg["ding"]["id"] == zwei["id"]


def test_gleicher_zustand_fragt_nicht(client):
    keller = _platz(client, "Keller")
    _ein(client, bereich="technik", code=EAN, name="Stick")
    _ein(client, bereich="technik", code=EAN, bestaetigt=True)
    assert _lagern(client, richtung="ein", code=EAN, platz_id=keller["id"])["art"] == "gebucht"


def test_unbekannter_code(client):
    assert _lagern(client, richtung="aus", code=EAN2)["art"] == "unbekannt"


# ---------------------------------------------------------------------------
# Fotos
# ---------------------------------------------------------------------------

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64


def test_foto_hochladen_zeigen_ersetzen_loeschen(client, foto_ablage):
    s = _ein(client, bereich="technik", name="Kamera")["sache"]
    r = client.post(f"/api/sachen/{s['id']}/foto", content=JPEG,
                    headers={"Content-Type": "image/jpeg"})
    assert r.status_code == 200, r.text
    erst = r.json()["foto"]
    assert (foto_ablage / erst).is_file()
    r = client.get(f"/api/sachen/{s['id']}/foto")
    assert r.status_code == 200 and r.content == JPEG
    assert r.headers["x-content-type-options"] == "nosniff"

    zweit = client.post(f"/api/sachen/{s['id']}/foto", content=JPEG + b"1").json()["foto"]
    assert zweit != erst and not (foto_ablage / erst).exists()

    assert client.delete(f"/api/sachen/{s['id']}/foto").status_code == 204
    assert not (foto_ablage / zweit).exists()
    assert client.get(f"/api/sachen/{s['id']}/foto").status_code == 422


def test_nur_jpeg(client, foto_ablage):
    s = _ein(client, bereich="technik", name="Kamera")["sache"]
    r = client.post(f"/api/sachen/{s['id']}/foto", content=b"<svg onload=alert(1)>")
    assert r.status_code == 422
    assert not foto_ablage.exists() or not any(foto_ablage.iterdir())


def test_sache_loeschen_nimmt_das_foto_mit(client, foto_ablage):
    s = _ein(client, bereich="technik", name="Kamera")["sache"]
    name = client.post(f"/api/sachen/{s['id']}/foto", content=JPEG).json()["foto"]
    client.delete(f"/api/electronics/{s['id']}")
    assert not (foto_ablage / name).exists()


def test_kontoloeschung_nennt_die_fotos(db_session, client, foto_ablage):
    from app import konto

    s = _ein(client, bereich="technik", name="Kamera")["sache"]
    name = client.post(f"/api/sachen/{s['id']}/foto", content=JPEG).json()["foto"]
    sub = db_session.execute(
        __import__("sqlalchemy").text("SELECT owner_sub FROM sache WHERE id = :i"), {"i": s["id"]}
    ).scalar_one()
    pfade = konto.foto_dateien(db_session, sub)
    assert [p.name for p in pfade] == [name]


# ---------------------------------------------------------------------------
# Zuruecknehmen: ein Fehlscan aus der Quittung (Projectdeck 172)
# ---------------------------------------------------------------------------

def _zurueck(client, weg, **body):
    return client.post(f"/api/laeufe/{weg}/zuruecknehmen", json=body)


def test_eingebuchter_posten_geht_wieder(client):
    _produkt(client)
    p = _ein(client, code=EAN, menge=2)["posten"]
    r = _zurueck(client, "einbuchen", posten_id=p["id"])
    assert r.status_code == 200 and "Joghurt" in r.json()["text"]
    assert client.get(f"/api/stock/{p['id']}").status_code in (404, 422)
    # Das Produkt bleibt: der naechste Scan desselben Codes findet es.
    assert _ein(client, code=EAN)["art"] == "neu"


def test_verbrauchter_posten_wird_nicht_zurueckgenommen(client):
    prod = _produkt(client)
    p = _ein(client, code=EAN, menge=3)["posten"]
    r = client.post("/api/stock/consume", json={"product_id": prod["id"], "amount": 1, "unit": "piece"})
    assert r.status_code in (200, 201), r.text
    r = _zurueck(client, "einbuchen", posten_id=p["id"])
    assert r.status_code == 422 and "verbraucht" in r.text


def test_nach_dem_einkauf_kein_zuruecknehmen(client):
    _produkt(client)
    p = _ein(client, code=EAN)["posten"]
    client.post("/api/laeufe/abschluss", json={"bereich": "lebensmittel", "posten": [p["id"]],
                                              "laden": "Kaufland"})
    assert _zurueck(client, "einbuchen", posten_id=p["id"]).status_code == 422


def test_sache_geht_wieder_mit_foto_und_kennung_bleibt_verbraucht(client, foto_ablage):
    s = _ein(client, bereich="technik", name="Kamera")["sache"]
    name = client.post(f"/api/sachen/{s['id']}/foto", content=JPEG).json()["foto"]
    r = _zurueck(client, "einbuchen", sache_id=s["id"])
    assert r.status_code == 200 and s["kennung"] in r.json()["text"]
    assert not (foto_ablage / name).exists()
    # Ein Etikett klebt vielleicht schon: die Kennung wird nie neu vergeben.
    assert _ein(client, bereich="technik", name="Kamera")["sache"]["kennung"] != s["kennung"]


def test_genau_eins_angeben(client):
    assert _zurueck(client, "einbuchen").status_code == 422
    assert _zurueck(client, "einbuchen", posten_id=1, sache_id=1).status_code == 422


def test_lagern_zuruecknehmen_posten_kommt_ins_alte_fach(client):
    keller = _platz(client, "Keller")
    kueche = _platz(client, "Küche")
    _produkt(client)
    p = _ein(client, code=EAN, platz_id=keller["id"])["posten"]
    erg = _lagern(client, richtung="um", code=EAN, platz_id=kueche["id"])
    assert erg["vorher_platz_id"] == keller["id"]
    r = _zurueck(client, "lagern", posten_id=p["id"], vorher_platz_id=erg["vorher_platz_id"])
    assert r.status_code == 200 and r.json()["ding"]["platz_id"] == keller["id"]


def test_lagern_zuruecknehmen_sache_bekommt_verbleib_und_grund_zurueck(client):
    keller = _platz(client, "Keller")
    s = _ein(client, bereich="technik", code=EAN, name="Akkuschrauber")["sache"]
    _lagern(client, richtung="ein", code=EAN, platz_id=keller["id"])
    _lagern(client, richtung="aus", code="S-0001", grund="im_einsatz")
    erg = _lagern(client, richtung="ein", code="S-0001", platz_id=keller["id"])
    assert erg["vorher_verbleib"] == "shopfloor" and erg["vorher_grund"] == "im_einsatz"
    r = _zurueck(client, "lagern", sache_id=s["id"], vorher_platz_id=erg["vorher_platz_id"],
                 vorher_verbleib=erg["vorher_verbleib"], vorher_grund=erg["vorher_grund"])
    assert r.status_code == 200
    a = client.get(f"/api/electronics/{s['id']}").json()
    assert a["verbleib"] == "shopfloor" and a["shopfloor_grund"] == "im_einsatz"
    assert a["platz_id"] == keller["id"]
