"""Filme & Medien (Stufe 5a): Exemplare mit Titel aus medien, Spiegel, Gruende je Bereich.

medien ist hier eine Attrappe (`_ruf` ersetzt): geprueft wird, was das Lager
schickt und wie es mit den Antworten umgeht, nicht medien selbst.
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.domain import DomainError
from app.services import medien

EAN = "4010232051776"


class Attrappe:
    def __init__(self):
        self.katalog = {7: {"id": 7, "titel": "Two and a Half Men", "medientyp": "Serie"}}
        self.aufrufe: list[tuple[str, str, dict]] = []
        self.aus = False
        self.abgaenge: list[dict] = []
        self.isbn = {"9783499226601": "Der Name der Rose"}

    def __call__(self, methode, pfad, **kw):
        self.aufrufe.append((methode, pfad, kw))
        if self.aus:
            raise medien.NichtErreichbar("medien ist gerade nicht erreichbar.", {})
        if pfad == "/api/lager/titel" and methode == "GET":
            q = kw["params"]["q"].lower()
            return [t for t in self.katalog.values() if q in t["titel"].lower()]
        if pfad == "/api/lager/titel" and methode == "POST":
            name = kw["json"]["titel"]
            if not name and kw["json"].get("isbn"):
                # medien: Katalog, sonst DNB und Open Library; unbekannt = 422
                name = self.isbn.get(kw["json"]["isbn"])
                if name is None:
                    raise DomainError("medien antwortet 422", {"status": 422})
            for t in self.katalog.values():
                if t["titel"].lower() == name.lower():
                    return {**t, "neu": False}
            nr = max(self.katalog) + 1
            self.katalog[nr] = {"id": nr, "titel": name, "medientyp": kw["json"]["medientyp"]}
            return {**self.katalog[nr], "neu": True}
        if pfad == "/api/lager/abgaenge":
            return {"abgaenge": self.abgaenge}
        if pfad == "/api/lager/bestand":
            return {"anzahl": len(kw["json"]["stuecke"])}
        raise AssertionError(pfad)


@pytest.fixture
def katalog(monkeypatch):
    a = Attrappe()
    monkeypatch.setattr(settings, "MEDIEN_BASE_URL", "http://medien:8000")
    monkeypatch.setattr(settings, "MEDIEN_TOKEN", "probe")
    monkeypatch.setattr(medien, "_ruf", a)
    monkeypatch.setattr(medien, "verbindung", medien.Verbindung())
    # Der Spiegel-Laeufer bleibt in Tests aus; gesendet wird von Hand.
    monkeypatch.setattr(medien, "anstossen", lambda: None)
    monkeypatch.setattr(medien, "starten", lambda: None)
    return a


def _ein(client, **body):
    body.setdefault("bereich", "medien")
    r = client.post("/api/laeufe/einbuchen", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _bereich(client, schluessel):
    return next(b for b in client.get("/api/bereiche").json() if b["schluessel"] == schluessel)


def test_ohne_anbindung_ausgegraut_mit_einem_satz(client):
    b = _bereich(client, "medien")
    assert b["bereit"] is False and "Schlüssel" in b["satz"]["text"]
    r = client.post("/api/laeufe/einbuchen", json={"bereich": "medien", "name": "Alien"})
    assert r.status_code == 422


def test_mit_anbindung_offen(client, katalog):
    b = _bereich(client, "medien")
    assert b["bereit"] is True and b["bauart"] == "exemplar"
    assert [g["schluessel"] for g in b["gruende"]] == ["rippen", "schauen", "verkauf_vorbereiten"]


def test_huelle_mit_staffel_wird_teil_und_titel_aus_medien(client, katalog):
    erg = _ein(client, code=EAN, name="Two and a Half Men – Staffel 3", medium="DVD",
               medientyp="Serie")
    assert erg["art"] == "neu"
    s = erg["sache"]
    assert s["titel_id"] is not None and s["teil"] == "Staffel 3" and s["medium"] == "DVD"
    assert s["kennung"] == "S-0001" and s["condition"] == "Ungeprüft"
    # Den Titel hat medien zugeordnet bzw. angelegt, nicht das Lager.
    assert ("POST", "/api/lager/titel") in [(m, p) for m, p, _ in katalog.aufrufe]


def test_gewaehlter_katalogtitel(client, katalog):
    erg = _ein(client, titel_id=7, katalogtitel="Two and a Half Men",
               name="Two and a Half Men – Staffel 4", medium="Blu-ray")
    # Name = Katalogtitel, die Staffel kommt aus der Huelle.
    assert erg["sache"]["titel_id"] == 7 and erg["sache"]["name"] == "Two and a Half Men"
    assert erg["sache"]["teil"] == "Staffel 4"
    assert not [p for m, p, _ in katalog.aufrufe if m == "POST"]


def test_unbekannter_strichcode_fragt_nach_dem_titel(client, katalog):
    assert _ein(client, code=EAN)["art"] == "name_fehlt"


def test_zweite_scheibe_desselben_titels_ist_bekannt(client, katalog):
    _ein(client, code=EAN, titel_id=7, name="Two and a Half Men")
    erg = _ein(client, code=EAN)
    assert erg["art"] == "bekannt" and erg["vorhanden"][0]["titel_id"] == 7
    erg = _ein(client, code=EAN, bestaetigt=True)
    assert erg["art"] == "neu" and erg["sache"]["titel_id"] == 7


def test_dvd_strichcode_ist_im_technik_lauf_unbekannt(client, katalog):
    """Treffer nur im eigenen Bereich."""
    _ein(client, code=EAN, titel_id=7, name="Two and a Half Men")
    r = client.post("/api/laeufe/einbuchen", json={"bereich": "technik", "code": EAN})
    assert r.json()["art"] == "name_fehlt"


def test_medien_aus_bucht_trotzdem_ein_und_traegt_den_titel_nach(client, katalog, db_session):
    """Seit 2026-11-01: ein Neustart von medien bricht den Lauf nicht mehr ab."""
    katalog.aus = True
    erg = _ein(client, code=EAN, name="Two and a Half Men – Staffel 5", medium="DVD")
    assert erg["art"] == "neu" and erg["titel_offen"] is True
    s = erg["sache"]
    assert s["titel_id"] is None and s["teil"] == "Staffel 5"
    assert medien.ohne_titel(db_session) == 1
    # Noch aus: der Nachtrag bricht ab und laesst das Stueck stehen.
    with pytest.raises(medien.NichtErreichbar):
        medien.titel_nachtragen(db_session)
    katalog.aus = False
    assert medien.titel_nachtragen(db_session) == 1
    db_session.expire_all()
    s = client.get("/api/electronics", params={"bereich": "medien"}).json()["items"][0]
    # medien bekam die Huelle und hat die Staffel abgeschnitten (hier: Attrappe
    # findet den Katalogtitel ueber den Namen ohne Staffel nicht, legt also an).
    assert s["titel_id"] is not None and s["teil"] == "Staffel 5"
    assert medien.ohne_titel(db_session) == 0


def test_kachel_sagt_wenn_titel_fehlen_und_wenn_medien_schweigt(client, katalog, monkeypatch):
    katalog.aus = True
    _ein(client, name="Alien", medium="DVD")
    assert _bereich(client, "medien")["satz"]["schluessel"] == "ohne_titel"
    v = medien.Verbindung()
    v.gescheitert("medien ist gerade nicht erreichbar.")
    monkeypatch.setattr(medien, "verbindung", v)
    satz = _bereich(client, "medien")["satz"]
    assert satz["schluessel"] == "getrennt" and "antwortet seit" in satz["text"]
    assert "1 Stück wartet auf den Titel" in satz["text"]


def test_nach_fehlschlag_kuerzer_warten(monkeypatch):
    v = medien.Verbindung()
    monkeypatch.setattr(medien, "verbindung", v)
    assert medien._pause() == medien.SPIEGEL_TAKT
    pausen = []
    for _ in range(6):
        v.gescheitert("x")
        pausen.append(medien._pause())
    assert pausen == [60, 120, 240, 480, 900, 900]
    seit = v.fehler_seit
    v.gescheitert("y")
    assert v.fehler_seit == seit  # der Beginn des Ausfalls bleibt stehen
    v.ok()
    assert v.fehler_seit is None and medien._pause() == medien.SPIEGEL_TAKT


def test_titelverweis_nur_bei_filmen(client, katalog):
    b = _bereich(client, "medien")
    assert b["titel_verweis"] == "https://medien.home.arpa/#titel/{titel_id}"
    assert _bereich(client, "technik")["titel_verweis"] is None


def test_titelsuche_geht_durchs_lager(client, katalog):
    r = client.get("/api/medien/titel", params={"q": "half"})
    assert r.status_code == 200 and r.json()[0]["id"] == 7


def test_filme_nicht_in_der_technik_liste(client, katalog):
    _ein(client, titel_id=7, name="Two and a Half Men")
    assert client.get("/api/electronics").json()["total"] == 0
    assert client.get("/api/electronics", params={"bereich": "medien"}).json()["total"] == 1


def test_gruende_je_bereich(client, katalog):
    keller = client.post("/api/plaetze", json={"name": "Keller", "art": "raum"}).json()
    _ein(client, code=EAN, titel_id=7, name="Two and a Half Men", platz_id=keller["id"])
    erg = client.post("/api/laeufe/lagern", json={"richtung": "aus", "code": EAN,
                                                  "grund": "reparatur"}).json()
    assert erg["art"] == "grund_fehlt" and erg["bereich"] == "medien"
    assert erg["gruende"] == ["rippen", "schauen", "verkauf_vorbereiten"]
    erg = client.post("/api/laeufe/lagern", json={"richtung": "aus", "code": EAN,
                                                  "grund": "rippen"}).json()
    assert erg["art"] == "gebucht" and erg["ding"]["shopfloor_grund"] == "rippen"


def test_grund_aus_fremdem_bereich_auch_am_formular_abgewiesen(client, katalog):
    s = _ein(client, titel_id=7, name="Two and a Half Men")["sache"]
    r = client.put(f"/api/electronics/{s['id']}", json={"shopfloor_grund": "reparatur"})
    assert r.status_code == 422


def test_spiegel_enthaelt_nur_filme_mit_allem_was_medien_braucht(client, katalog, db_session):
    _ein(client, code=EAN, titel_id=7, name="Two and a Half Men – Staffel 2", medium="DVD",
         zustand="Gut", preis=4.5)
    client.post("/api/laeufe/einbuchen", json={"bereich": "technik", "name": "Bohrer"})
    stuecke = medien.abzug(db_session)
    assert len(stuecke) == 1
    s = stuecke[0]
    assert (s["kennung"], s["titel_id"], s["teil"], s["medium"], s["zustand"], s["einstand"]) == \
        ("S-0001", 7, "Staffel 2", "DVD", "Gut", 4.5)
    assert s["verbleib"] == "shopfloor" and s["platz"] is None


def test_fremder_mandant_sieht_den_bereich_zu(client, katalog, db_session, monkeypatch):
    monkeypatch.setattr(settings, "DEFAULT_OWNER_SUB", "owner")
    db_session.info["owner_sub"] = "gast"
    assert medien.offen(db_session) is False
    with pytest.raises(DomainError):
        medien.pruefe_offen(db_session)
    db_session.info["owner_sub"] = "owner"
    assert medien.offen(db_session) is True


def test_zuruecknehmen_eines_films_stoesst_den_spiegel_an(client, katalog, monkeypatch):
    """Ein zurueckgenommener Fehlscan stand sonst bis zum naechsten Takt in medien."""
    angestossen: list[int] = []
    monkeypatch.setattr(medien, "anstossen", lambda: angestossen.append(1))
    s = _ein(client, titel_id=7, name="Two and a Half Men")["sache"]
    vorher = len(angestossen)
    r = client.post("/api/laeufe/einbuchen/zuruecknehmen", json={"sache_id": s["id"]})
    assert r.status_code == 200, r.text
    assert len(angestossen) == vorher + 1


# ---------------------------------------------------------------------------
# Bücher über die ISBN (2026-11-07, medien RICHTUNG Stufe 6)
# ---------------------------------------------------------------------------

ISBN = "9783499226601"


@pytest.fixture
def ohne_upc():
    from unittest.mock import AsyncMock, patch

    with patch("app.api.routes_laeufe.BarcodeService.lookup_film", new=AsyncMock(return_value=None)) as m:
        yield m


def test_isbn_scan_bucht_das_buch_ohne_rueckfrage(client, katalog, ohne_upc):
    erg = _ein(client, code=ISBN)
    assert erg["art"] == "neu"
    s = erg["sache"]
    assert s["name"] == "Der Name der Rose" and s["medium"] == "Buch" and s["medientyp"] == "Buch"
    post = [kw["json"] for m, p, kw in katalog.aufrufe if m == "POST"]
    assert post == [{"titel": "", "medientyp": "Buch", "isbn": ISBN}]
    # Nie UPCitemdb fuer ein Buch.
    ohne_upc.assert_not_called()


def test_eingetippte_isbn10_ist_kein_seriennummer(client, katalog, ohne_upc):
    erg = _ein(client, code="3-499-22660-X")
    assert erg["art"] == "neu"
    assert erg["sache"]["barcode"] == ISBN and erg["sache"].get("serial") in (None, "")


def test_zweites_exemplar_per_isbn_ist_bekannt(client, katalog, ohne_upc):
    _ein(client, code=ISBN)
    assert _ein(client, code=ISBN)["art"] == "bekannt"


def test_unbekannte_isbn_fragt_mit_hinweis_und_traegt_die_isbn_mit(client, katalog, ohne_upc):
    erg = _ein(client, code="9783161484100")
    assert erg["art"] == "name_fehlt" and "ISBN" in erg["hinweis"]
    ohne_upc.assert_not_called()
    erg = _ein(client, code="9783161484100", name="Ein altes Buch")
    assert erg["art"] == "neu" and erg["sache"]["medium"] == "Buch"
    assert [kw["json"] for m, p, kw in katalog.aufrufe if m == "POST"][-1]["isbn"] == "9783161484100"


def test_isbn_bei_stummem_medien_fragt_nach_dem_titel(client, katalog, ohne_upc):
    katalog.aus = True
    erg = _ein(client, code=ISBN)
    assert erg["art"] == "name_fehlt" and "medien" in erg["hinweis"]
    erg = _ein(client, code=ISBN, name="Der Name der Rose")
    assert erg["art"] == "neu" and erg["titel_offen"] is True


def test_medium_ohne_vorgabe_und_medientyp_zum_medium(client, katalog, ohne_upc):
    # Ohne Vorgabe (alte App): eine Scheibe ist eine DVD.
    assert _ein(client, code=EAN, name="Alien")["sache"]["medium"] == "DVD"
    erg = _ein(client, name="Abbey Road", medium="CD")
    assert erg["sache"]["medium"] == "CD" and erg["sache"]["medientyp"] == "Musik"


def test_isbn_im_technik_lauf_bleibt_strichcode_ohne_medien(client, katalog):
    from unittest.mock import AsyncMock, patch

    with patch("app.api.routes_laeufe.BarcodeService.lookup", new=AsyncMock(return_value=None)):
        r = client.post("/api/laeufe/einbuchen", json={"bereich": "technik", "code": ISBN})
    assert r.json()["art"] == "name_fehlt"
    assert not [p for m, p, _ in katalog.aufrufe if m == "POST"]


def test_lagern_nur_was_eingebucht_ist_auch_per_isbn10(client, katalog, ohne_upc):
    """Owner 2026-11-07: Lagern kann man nur, was im Bestand ist."""
    platz = client.post("/api/plaetze", json={"name": "Arbeitszimmer", "art": "raum"}).json()
    lag = {"richtung": "ein", "code": "3-499-22660-X", "platz_id": platz["id"]}
    assert client.post("/api/laeufe/lagern", json=lag).json()["art"] == "unbekannt"
    _ein(client, code=ISBN)
    r = client.post("/api/laeufe/lagern", json=lag)
    assert r.status_code == 200 and r.json()["art"] not in ("unbekannt", "passt_nicht"), r.text


def test_quittung_aendert_staffel_edition_einband(client, katalog, ohne_upc, db_session):
    """2026-11-07: Staffel, Edition und Einband in der Quittung der Lager-App."""
    s = _ein(client, code=ISBN)["sache"]
    r = client.put(f"/api/electronics/{s['id']}", json={"einband": "Hardcover", "edition": " Erstausgabe "})
    assert r.status_code == 200, r.text
    assert r.json()["einband"] == "Hardcover" and r.json()["edition"] == "Erstausgabe"
    # Leer geschickt = geleert; nicht geschickt = bleibt.
    r = client.put(f"/api/electronics/{s['id']}", json={"edition": ""})
    assert r.json()["edition"] is None and r.json()["einband"] == "Hardcover"
    assert client.put(f"/api/electronics/{s['id']}", json={"medium": ""}).status_code == 422
    stueck = next(x for x in medien.abzug(db_session) if x["kennung"] == s["kennung"])
    assert stueck["einband"] == "Hardcover"


def test_staffel_nur_bei_filmen_und_medien(client):
    r = client.post("/api/laeufe/einbuchen", json={"bereich": "technik", "name": "Akkuschrauber"})
    sid = r.json()["sache"]["id"]
    assert client.put(f"/api/electronics/{sid}", json={"teil": "Staffel 1"}).status_code == 422
