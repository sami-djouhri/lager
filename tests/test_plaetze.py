"""Plaetze: feste Verschachtelung, Kennung, Kisten, Shopfloor, alter Ortstext."""

from __future__ import annotations


def _platz(client, name, art, eltern=None, **mehr):
    resp = client.post("/api/plaetze", json={"name": name, "art": art, "eltern_id": eltern, **mehr})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _produkt(client):
    return client.post("/api/products", json={"name": "Reis", "default_unit": "g"}).json()["id"]


def test_verschachtelung_raum_regal_fach_kiste(client):
    raum = _platz(client, "Keller", "raum")
    regal = _platz(client, "Regal A", "regal", raum["id"])
    fach = _platz(client, "Fach 2", "fach", regal["id"])
    kiste = _platz(client, "Kiste 1", "kiste", fach["id"])
    assert kiste["pfad"] == "Keller › Regal A › Fach 2 › Kiste 1"
    assert [p["kennung"] for p in (raum, regal, fach, kiste)] == ["L-001", "L-002", "L-003", "L-004"]
    # Eine Kiste darf auch direkt im Raum stehen.
    _platz(client, "Kiste 2", "kiste", raum["id"])


def test_verbotene_verschachtelung(client):
    raum = _platz(client, "Keller", "raum")
    kiste = _platz(client, "Kiste", "kiste", raum["id"])
    for name, art, eltern in (
        ("Kiste in Kiste", "kiste", kiste["id"]),
        ("Fach im Raum", "fach", raum["id"]),
        ("Regal ohne Raum", "regal", None),
        ("Raum im Raum", "raum", raum["id"]),
    ):
        resp = client.post("/api/plaetze", json={"name": name, "art": art, "eltern_id": eltern})
        assert resp.status_code == 422, name


def test_kennung_wird_nach_dem_loeschen_nicht_neu_vergeben(client):
    _platz(client, "A", "raum")
    b = _platz(client, "B", "raum")
    assert client.delete(f"/api/plaetze/{b['id']}").status_code == 204
    # L-002 klebt vielleicht noch als Etikett irgendwo.
    assert _platz(client, "C", "raum")["kennung"] == "L-003"


def test_nicht_leerer_platz_laesst_sich_nicht_loeschen(client):
    raum = _platz(client, "Keller", "raum")
    client.post("/api/stock", json={"product_id": _produkt(client), "quantity": 5, "unit": "g",
                                    "platz_id": raum["id"]})
    resp = client.delete(f"/api/plaetze/{raum['id']}")
    assert resp.status_code == 422
    assert resp.json()["details"]["posten"] == 1


def test_kiste_zieht_mit_inhalt_um(client):
    keller = _platz(client, "Keller", "raum")
    boden = _platz(client, "Dachboden", "raum")
    kiste = _platz(client, "Deko", "kiste", keller["id"], bereich="saison", inhalt="Kugeln")
    sid = client.post("/api/electronics", json={"name": "Lichterkette",
                                                "platz_id": kiste["id"]}).json()["id"]
    resp = client.put(f"/api/plaetze/{kiste['id']}", json={"eltern_id": boden["id"]})
    assert resp.status_code == 200
    assert resp.json()["pfad"] == "Dachboden › Deko"
    sache = client.get(f"/api/electronics/{sid}").json()
    assert sache["platz_pfad"] == "Dachboden › Deko"
    assert sache["platz_kennung"] == kiste["kennung"]


def test_kistenfelder_nur_an_kisten(client):
    resp = client.post("/api/plaetze", json={"name": "Keller", "art": "raum", "inhalt": "x"})
    assert resp.status_code == 422
    raum = _platz(client, "Keller", "raum")
    resp = client.post("/api/plaetze", json={"name": "K", "art": "kiste", "eltern_id": raum["id"],
                                             "bereich": "lebensmittel"})
    assert resp.status_code == 422


def test_inhalt_eines_platzes_mischt_die_bereiche(client):
    raum = _platz(client, "Abstellraum", "raum")
    client.post("/api/stock", json={"product_id": _produkt(client), "quantity": 5, "unit": "g",
                                    "platz_id": raum["id"]})
    client.post("/api/electronics", json={"name": "Staubsauger", "platz_id": raum["id"]})
    inhalt = client.get(f"/api/plaetze/{raum['id']}").json()
    assert sorted((d["art"], d["name"]) for d in inhalt["dinge"]) == [
        ("posten", "Reis"), ("sache", "Staubsauger"),
    ]
    assert inhalt["platz"]["posten"] == 1
    assert inhalt["platz"]["sachen"] == 1


def test_alter_ortstext_wird_ein_raum(client):
    # So bucht die Lager-App 0.1.0 ein.
    pid = _produkt(client)
    a = client.post("/api/stock", json={"product_id": pid, "quantity": 5, "unit": "g",
                                        "location": "Kühlschrank"}).json()
    b = client.post("/api/stock", json={"product_id": pid, "quantity": 5, "unit": "g",
                                        "location": "kühlschrank"}).json()
    assert a["location"] == "Kühlschrank"
    assert a["platz_id"] == b["platz_id"]
    plaetze = client.get("/api/plaetze").json()
    assert [(p["name"], p["art"]) for p in plaetze] == [("Kühlschrank", "raum")]


def test_ortstext_trifft_den_altort_trotz_umlaut(client):
    # Migriert heisst der Raum „Kuehlschrank", die App schickt „Kühlschrank".
    raum = _platz(client, "Kuehlschrank", "raum")
    e = client.post("/api/stock", json={"product_id": _produkt(client), "quantity": 5,
                                        "unit": "g", "location": "Kühlschrank"}).json()
    assert e["platz_id"] == raum["id"]
    assert len(client.get("/api/plaetze").json()) == 1


def test_shopfloor(client):
    pid = _produkt(client)
    client.post("/api/stock", json={"product_id": pid, "quantity": 5, "unit": "g"})
    client.post("/api/electronics", json={"name": "Laptop", "shopfloor_grund": "im_einsatz"})
    client.post("/api/electronics", json={"name": "Kabel"})
    raum = _platz(client, "Keller", "raum")
    client.post("/api/electronics", json={"name": "Drucker", "platz_id": raum["id"]})

    sf = client.get("/api/shopfloor").json()
    gruppen = {g["grund"]: [d["name"] for d in g["dinge"]] for g in sf["gruppen"]}
    assert gruppen[None] == ["Kabel", "Reis"]
    assert gruppen["im_einsatz"] == ["Laptop"]
    assert sf["anzahl"] == 3
    assert sf["gruppen"][0]["grund"] is None


def test_posten_ohne_platz_heisst_nicht_eingelagert(client):
    e = client.post("/api/stock", json={"product_id": _produkt(client), "quantity": 5,
                                        "unit": "g"}).json()
    assert e["platz_id"] is None
    assert e["location"] == "nicht eingelagert"


def test_posten_zurueck_auf_den_shopfloor_und_verlauf(client, db_session):
    from app.models import Verlauf

    raum = _platz(client, "Keller", "raum")
    eid = client.post("/api/stock", json={"product_id": _produkt(client), "quantity": 5,
                                          "unit": "g", "platz_id": raum["id"]}).json()["id"]
    d = client.put(f"/api/stock/{eid}", json={"platz_id": None}).json()
    assert d["platz_id"] is None
    zeilen = db_session.query(Verlauf).filter_by(ziel="posten", ziel_id=eid).all()
    assert [(z.feld, z.alt, z.neu) for z in zeilen] == [("platz_id", str(raum["id"]), None)]


def test_per_kennung(client):
    raum = _platz(client, "Keller", "raum")
    assert client.get("/api/plaetze/kennung/l-1").json()["id"] == raum["id"]
    assert client.get("/api/plaetze/kennung/L-999").status_code == 422


def test_suche_findet_posten_sachen_und_plaetze(client):
    keller = _platz(client, "Keller", "raum")
    _platz(client, "Deko", "kiste", keller["id"], bereich="saison", inhalt="Kugeln, Lichterkette")
    pid = client.post("/api/products", json={"name": "Käse Gouda", "default_unit": "g",
                                              "barcode": "4001234567890"}).json()["id"]
    client.post("/api/stock", json={"product_id": pid, "quantity": 200, "unit": "g",
                                    "platz_id": keller["id"]})
    sache = client.post("/api/electronics", json={"name": "Lötkolben", "brand": "Weller"}).json()

    # Umlaut gefaltet, Gross/Klein egal; Ort steht als Pfad dabei.
    r = client.get("/api/suche", params={"q": "KAESE"}).json()
    assert [d["name"] for d in r["dinge"]] == ["Käse Gouda"]
    assert r["dinge"][0]["platz_pfad"] == "Keller"

    # Strichcode genau, Kennung genau, Marke als Teilwort.
    assert client.get("/api/suche", params={"q": "4001234567890"}).json()["dinge"][0]["art"] == "posten"
    assert client.get("/api/suche", params={"q": sache["kennung"]}).json()["dinge"][0]["id"] == sache["id"]
    assert client.get("/api/suche", params={"q": "weller"}).json()["dinge"][0]["name"] == "Lötkolben"

    # Kisteninhalt und Platz-Kennung finden den Platz.
    assert [p["name"] for p in client.get("/api/suche", params={"q": "lichter"}).json()["plaetze"]] == ["Deko"]
    assert client.get("/api/suche", params={"q": "l-001"}).json()["plaetze"][0]["name"] == "Keller"


def test_suche_laesst_leere_posten_weg_und_ordnet_genau_vor_teilwort(client):
    a = client.post("/api/products", json={"name": "Reis", "default_unit": "g"}).json()["id"]
    b = client.post("/api/products", json={"name": "Milchreis", "default_unit": "g"}).json()["id"]
    leer = client.post("/api/products", json={"name": "Reisnudeln", "default_unit": "g"}).json()["id"]
    for pid, menge in ((a, 500), (b, 100), (leer, 100)):
        client.post("/api/stock", json={"product_id": pid, "quantity": menge, "unit": "g"})
    client.post("/api/stock/consume", json={"product_id": leer, "amount": 100, "unit": "g",
                                            "reason": "verbraucht"})
    r = client.get("/api/suche", params={"q": "reis"}).json()
    # Anfang vor Teilwort, ein aufgebrauchter Posten ist kein Fundort.
    assert [d["name"] for d in r["dinge"]] == ["Reis", "Milchreis"]
    assert r["dinge"][0]["platz_pfad"] == ""
    assert client.get("/api/suche", params={"q": ""}).status_code == 422
