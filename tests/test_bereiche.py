"""Bereiche: feste Liste, Trennung der Vorräte, ein Satz je Kachel."""

from datetime import date, timedelta

from app.bereiche import BEREICHE, VORRAT_SCHLUESSEL


def _produkt(client, name, bereich=None, **extra):
    body = {"name": name, "default_unit": "piece", **extra}
    if bereich:
        body["bereich"] = bereich
    resp = client.post("/api/products", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _posten(client, pid, tage=None, menge=1):
    body = {"product_id": pid, "quantity": menge, "unit": "piece"}
    if tage is not None:
        body["mhd"] = (date.today() + timedelta(days=tage)).isoformat()
    assert client.post("/api/stock", json=body).status_code == 201


def _saetze(client):
    return {b["schluessel"]: b for b in client.get("/api/bereiche").json()}


def test_liste_fest_und_in_reihenfolge(client):
    antwort = client.get("/api/bereiche").json()
    assert [b["schluessel"] for b in antwort] == [b.schluessel for b in BEREICHE]
    assert len(antwort) == 10  # Filme & Medien seit Stufe 5


def test_altbestand_ist_lebensmittel(client):
    pid = _produkt(client, "Reis")
    assert client.get(f"/api/products/{pid}").json()["bereich"] == "lebensmittel"


def test_bereich_ohne_produkte_wird_abgewiesen(client):
    for falsch in ("technik", "kleidung", "gibtsnicht"):
        resp = client.post("/api/products", json={"name": f"X {falsch}", "bereich": falsch})
        assert resp.status_code == 422, falsch


def test_vorraete_mischen_sich_nicht(client):
    reis = _produkt(client, "Reis")
    pflaster = _produkt(client, "Pflaster", "apotheke")
    _posten(client, reis, 100)
    _posten(client, pflaster, -3)

    produkte = client.get("/api/products?bereich=apotheke").json()["items"]
    assert [p["name"] for p in produkte] == ["Pflaster"]
    suche = client.get("/api/products?q=e&bereich=lebensmittel").json()["items"]
    assert [p["name"] for p in suche] == ["Reis"]

    bestand = client.get("/api/stock?bereich=lebensmittel").json()["items"]
    assert [e["product_id"] for e in bestand] == [reis]

    frist = client.get("/api/stats/expiry-forecast?bereich=apotheke").json()
    assert [f["product_name"] for f in frist] == ["Pflaster"]


def test_saetze_rangfolge(client):
    """Was blockiert, steht vorn: vorbei vor bald vor knapp vor ruhig."""
    milch = _produkt(client, "Milch")
    _posten(client, milch, -1)
    saft = _produkt(client, "Saft", "getraenke")
    _posten(client, saft, 3)
    seife = _produkt(client, "Seife", "haushalt", min_stock=5)
    _posten(client, seife, None, menge=1)
    samen = _produkt(client, "Tomatensamen", "garten")
    _posten(client, samen, 400)

    s = _saetze(client)
    assert s["lebensmittel"]["satz"]["schluessel"] == "vorbei"
    assert s["lebensmittel"]["satz"]["blockiert"] is True
    assert "über dem MHD" in s["lebensmittel"]["satz"]["text"]
    assert s["getraenke"]["satz"]["schluessel"] == "bald"
    assert s["getraenke"]["satz"]["blockiert"] is False
    assert s["haushalt"]["satz"]["schluessel"] == "knapp"
    assert s["garten"]["satz"]["schluessel"] == "ruhig"
    assert s["apotheke"]["satz"]["schluessel"] == "leer"


def test_ungebaute_bereiche_nennen_ihre_stufe(client):
    s = _saetze(client)
    assert s["werkstatt"]["bereit"] is False
    assert s["werkstatt"]["satz"]["schluessel"] == "stufe"
    for schluessel in VORRAT_SCHLUESSEL | {"technik", "kleidung", "saison"}:
        assert s[schluessel]["bereit"] is True


def test_technik_satz_zaehlt_wie_das_portfolio(client):
    client.post("/api/electronics", json={
        "name": "Alter Laptop", "usage_status": "reserve", "estimated_resale_value": 200,
    })
    client.post("/api/electronics", json={
        "name": "Server", "usage_status": "critical", "estimated_resale_value": 900,
    })
    satz = _saetze(client)["technik"]["satz"]
    empfohlen = client.get("/api/electronics/portfolio").json()["resale_recommendations"]
    assert satz["schluessel"] == "verkauf"
    assert satz["anzahl"] == len(empfohlen) == 1


def test_vorratsbereiche_haben_orte(client):
    for b in client.get("/api/bereiche").json():
        if b["bauart"] == "vorrat":
            assert b["orte"], b["schluessel"]


def test_leerer_bereich_verweist_erst_auf_produkte(client):
    assert "Produkte" in _saetze(client)["apotheke"]["satz"]["text"]
    _produkt(client, "Pflaster", "apotheke")
    assert "Einbuchen" in _saetze(client)["apotheke"]["satz"]["text"]


def test_kisten_satz(client):
    s = _saetze(client)
    assert s["kleidung"]["satz"]["schluessel"] == "leer"
    raum = client.post("/api/plaetze", json={"name": "Dachboden", "art": "raum"}).json()
    client.post("/api/plaetze", json={"name": "Winterjacken", "art": "kiste",
                                     "eltern_id": raum["id"], "bereich": "kleidung"})
    s = _saetze(client)
    assert s["kleidung"]["satz"]["schluessel"] == "ohne_inhalt"
    assert s["saison"]["satz"]["schluessel"] == "leer"
