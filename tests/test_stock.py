"""Tests for stock entry management."""

from datetime import date, timedelta


def _setup_product(client, name="Reis"):
    resp = client.post("/api/products", json={"name": name, "default_unit": "g"})
    return resp.json()["id"]


def test_add_stock(client):
    pid = _setup_product(client)
    resp = client.post("/api/stock", json={
        "product_id": pid,
        "quantity": 500,
        "unit": "g",
        "mhd": "2026-06-01",
        "location": "Vorratskammer",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["product_id"] == pid
    assert data["quantity"] == 500
    assert data["product_name"] == "Reis"


def test_add_stock_unknown_product(client):
    resp = client.post("/api/stock", json={
        "product_id": 999, "quantity": 100, "unit": "g"
    })
    assert resp.status_code == 422


def test_list_stock(client):
    pid = _setup_product(client)
    client.post("/api/stock", json={"product_id": pid, "quantity": 500, "unit": "g"})
    client.post("/api/stock", json={"product_id": pid, "quantity": 300, "unit": "g"})

    resp = client.get("/api/stock")
    assert resp.status_code == 200
    page = resp.json()
    assert page["total"] == 2
    assert len(page["items"]) == 2


def test_list_stock_by_product(client):
    pid1 = _setup_product(client, "Reis")
    pid2 = _setup_product(client, "Nudeln")
    client.post("/api/stock", json={"product_id": pid1, "quantity": 500, "unit": "g"})
    client.post("/api/stock", json={"product_id": pid2, "quantity": 300, "unit": "g"})

    resp = client.get(f"/api/stock?product_id={pid1}")
    page = resp.json()
    assert page["total"] == 1
    assert page["items"][0]["product_name"] == "Reis"


def test_list_stock_by_location(client):
    pid = _setup_product(client)
    client.post("/api/stock", json={"product_id": pid, "quantity": 500, "unit": "g", "location": "Kuehlschrank"})
    client.post("/api/stock", json={"product_id": pid, "quantity": 300, "unit": "g", "location": "Vorratskammer"})

    resp = client.get("/api/stock?location=Kuehlschrank")
    assert resp.json()["total"] == 1


def test_update_stock(client):
    pid = _setup_product(client)
    create_resp = client.post("/api/stock", json={"product_id": pid, "quantity": 500, "unit": "g"})
    eid = create_resp.json()["id"]

    resp = client.put(f"/api/stock/{eid}", json={"quantity": 250, "location": "Kuehlschrank"})
    assert resp.status_code == 200
    assert resp.json()["quantity"] == 250
    assert resp.json()["location"] == "Kuehlschrank"


def test_delete_stock(client):
    pid = _setup_product(client)
    create_resp = client.post("/api/stock", json={"product_id": pid, "quantity": 500, "unit": "g"})
    eid = create_resp.json()["id"]

    resp = client.delete(f"/api/stock/{eid}")
    assert resp.status_code == 204

    resp = client.get("/api/stock")
    assert resp.json()["total"] == 0


def test_availability(client):
    pid = _setup_product(client)
    client.post("/api/stock", json={"product_id": pid, "quantity": 500, "unit": "g"})
    client.post("/api/stock", json={"product_id": pid, "quantity": 300, "unit": "g"})

    resp = client.get(f"/api/stock/available?product_id={pid}&unit=g")
    assert resp.status_code == 200
    assert resp.json()["total"] == 800


def test_expiring(client):
    pid = _setup_product(client)
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    far_future = (date.today() + timedelta(days=365)).isoformat()

    client.post("/api/stock", json={"product_id": pid, "quantity": 100, "unit": "g", "mhd": tomorrow})
    client.post("/api/stock", json={"product_id": pid, "quantity": 200, "unit": "g", "mhd": far_future})

    resp = client.get("/api/stock/expiring?days=7")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["quantity"] == 100


def test_days_until_expiry_computed(client):
    pid = _setup_product(client)
    in_5_days = (date.today() + timedelta(days=5)).isoformat()

    create_resp = client.post("/api/stock", json={
        "product_id": pid, "quantity": 100, "unit": "g", "mhd": in_5_days
    })
    data = create_resp.json()
    assert data["days_until_expiry"] == 5
