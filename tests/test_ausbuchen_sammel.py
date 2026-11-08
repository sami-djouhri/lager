"""Mehrfachauswahl im Bestand: mehrere Posten ganz ausbuchen (/api/stock/ausbuchen)."""

from datetime import date, timedelta


def _produkt(client, name):
    return client.post("/api/products", json={"name": name, "default_unit": "g"}).json()["id"]


def _posten(client, pid, menge, tage):
    mhd = (date.today() + timedelta(days=tage)).isoformat()
    body = {"product_id": pid, "quantity": menge, "unit": "g", "mhd": mhd}
    return client.post("/api/stock", json=body).json()["id"]


def _menge(client, entry_id):
    return client.get(f"/api/stock/{entry_id}").json()["quantity"]


def test_bucht_genau_die_gewaehlten_posten_ganz_aus(client):
    """Nicht FIFO: der juengere Posten bleibt stehen, auch wenn er aelter waere."""
    joghurt = _produkt(client, "Joghurt")
    milch = _produkt(client, "Milch")
    alt = _posten(client, joghurt, 500, -3)
    frisch = _posten(client, joghurt, 500, 10)
    milch_alt = _posten(client, milch, 1000, -1)

    resp = client.post("/api/stock/ausbuchen", json={"entry_ids": [alt, milch_alt]})
    assert resp.status_code == 200
    events = resp.json()
    assert {e["stock_entry_id"] for e in events} == {alt, milch_alt}
    assert all(e["reason"] == "abgelaufen" for e in events)
    assert sorted(e["amount"] for e in events) == [500, 1000]

    assert _menge(client, alt) == 0
    assert _menge(client, milch_alt) == 0
    assert _menge(client, frisch) == 500


def test_zaehlt_als_verlust(client):
    pid = _produkt(client, "Quark")
    eid = _posten(client, pid, 250, -2)
    client.post("/api/stock/ausbuchen", json={"entry_ids": [eid], "reason": "weggeworfen"})
    waste = client.get("/api/stats/waste").json()
    assert waste["total_events"] == 1


def test_alles_oder_nichts(client):
    """Ein unbekannter oder leerer Posten in der Auswahl: keiner wird gebucht."""
    pid = _produkt(client, "Sahne")
    gut = _posten(client, pid, 200, -1)
    leer = _posten(client, pid, 100, -1)
    client.post("/api/stock/ausbuchen", json={"entry_ids": [leer]})

    resp = client.post("/api/stock/ausbuchen", json={"entry_ids": [gut, leer, 99999]})
    assert resp.status_code == 422
    details = resp.json()["details"]
    assert details == {"fehlen": [99999], "leer": [leer]}
    assert _menge(client, gut) == 200


def test_doppelte_kennung_bucht_einmal(client):
    pid = _produkt(client, "Butter")
    eid = _posten(client, pid, 250, -1)
    resp = client.post("/api/stock/ausbuchen", json={"entry_ids": [eid, eid]})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_unbekannter_grund_und_leere_auswahl_abgelehnt(client):
    pid = _produkt(client, "Eier")
    eid = _posten(client, pid, 6, -1)
    assert client.post("/api/stock/ausbuchen", json={"entry_ids": [eid], "reason": "egal"}).status_code == 422
    assert client.post("/api/stock/ausbuchen", json={"entry_ids": []}).status_code == 422
    assert _menge(client, eid) == 6
