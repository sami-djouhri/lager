"""/api/preise: letzter Preis je Einheit fuer die Kostenschaetzung der Einkaufsliste."""


def _produkt(client, name, einheit="ml"):
    return client.post("/api/products", json={"name": name, "default_unit": einheit}).json()["id"]


def test_letzter_preis_je_einheit(client):
    milch = _produkt(client, "Milch")
    client.post("/api/stock", json={"product_id": milch, "quantity": 1000, "unit": "ml",
                                    "preis": 0.99})
    client.post("/api/stock", json={"product_id": milch, "quantity": 2000, "unit": "ml",
                                    "preis": 2.40})
    _produkt(client, "Salz", "g")  # ohne Preis: fehlt, statt geraten zu werden
    daten = client.get("/api/preise").json()
    assert daten == [{"product_id": milch, "unit": "ml", "preis_je_einheit": 0.0012,
                      "letzter_preis": 2.4, "letzte_menge": 2000.0, "je_kette": []}]


def test_posten_ohne_preis_zaehlt_nicht(client):
    brot = _produkt(client, "Brot", "piece")
    client.post("/api/stock", json={"product_id": brot, "quantity": 1, "unit": "piece"})
    assert client.get("/api/preise").json() == []


def _einkauf(client, posten, **abschluss):
    r = client.post("/api/laeufe/abschluss", json={"bereich": "lebensmittel", "posten": posten,
                                                  **abschluss})
    assert r.status_code == 200, r.text
    return r.json()


def _posten(client, produkt, menge, preis):
    return client.post("/api/stock", json={"product_id": produkt, "quantity": menge, "unit": "ml",
                                           "preis": preis}).json()["id"]


def test_letzter_preis_je_kette(client):
    milch = _produkt(client, "Milch")
    _einkauf(client, [_posten(client, milch, 1000, 1.19)], kette="lidl", am="2026-10-01")
    _einkauf(client, [_posten(client, milch, 1000, 0.99)], kette="lidl", am="2026-11-01")
    _einkauf(client, [_posten(client, milch, 1000, 1.09)], laden="Kaufland Mitte")
    _einkauf(client, [_posten(client, milch, 1000, 0.89)], laden="Bauernmarkt")
    _posten(client, milch, 1000, 1.49)  # ohne Einkauf: nur der letzte Preis
    [zeile] = client.get("/api/preise").json()
    assert zeile["letzter_preis"] == 1.49
    je = {k["kette"]: k for k in zeile["je_kette"]}
    assert set(je) == {"lidl", "kaufland"}  # Freitext ohne Kette vergleicht nichts
    assert je["lidl"]["letzter_preis"] == 0.99 and je["lidl"]["am"] == "2026-11-01"
    assert je["kaufland"]["preis_je_einheit"] == 0.00109


def test_kette_setzt_den_ladennamen(client):
    milch = _produkt(client, "Milch")
    e = _einkauf(client, [_posten(client, milch, 1000, 1.0)], kette="netto")
    assert e["kette"] == "netto" and e["laden"] == "Netto"


def test_unbekannte_kette_wird_abgewiesen(client):
    milch = _produkt(client, "Milch")
    r = client.post("/api/laeufe/abschluss", json={
        "bereich": "lebensmittel", "posten": [_posten(client, milch, 1000, 1.0)], "kette": "aldi"})
    assert r.status_code == 422
