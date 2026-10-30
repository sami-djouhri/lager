"""Tests for schema validation: max_length, unit normalisation."""


def test_unit_alias_normalised_on_stock_create(client):
    """'Gramm', 'kg', 'l' etc. werden via domain.normalise_unit auf {g, ml, piece} gemappt."""
    pid = client.post("/api/products", json={"name": "Mehl", "default_unit": "g"}).json()["id"]

    resp = client.post("/api/stock", json={
        "product_id": pid, "quantity": 500, "unit": "Gramm",
    })
    assert resp.status_code == 201
    assert resp.json()["unit"] == "g"


def test_unit_alias_normalised_on_consume(client):
    pid = client.post("/api/products", json={"name": "Reis", "default_unit": "g"}).json()["id"]
    client.post("/api/stock", json={"product_id": pid, "quantity": 1000, "unit": "g"})

    resp = client.post("/api/stock/consume", json={
        "product_id": pid, "amount": 100, "unit": "Gramm",
    })
    assert resp.status_code == 200


def test_product_name_max_length_enforced(client):
    too_long = "x" * 201
    resp = client.post("/api/products", json={"name": too_long, "default_unit": "g"})
    assert resp.status_code == 422


def test_stock_location_max_length_enforced(client):
    pid = client.post("/api/products", json={"name": "Test", "default_unit": "g"}).json()["id"]
    resp = client.post("/api/stock", json={
        "product_id": pid, "quantity": 100, "unit": "g", "location": "x" * 51,
    })
    assert resp.status_code == 422


def test_electronic_asset_notes_max_length_enforced(client):
    resp = client.post("/api/electronics", json={
        "name": "Asset", "notes": "x" * 2001,
    })
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Skalierende Aliase: 1 kg = 1000 g, 1 l = 1000 ml (Bug: Menge wurde nicht skaliert)
# ---------------------------------------------------------------------------

def test_kg_scales_quantity_on_stock_create(client):
    pid = client.post("/api/products", json={"name": "Zucker", "default_unit": "g"}).json()["id"]
    resp = client.post("/api/stock", json={"product_id": pid, "quantity": 1.5, "unit": "kg"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["unit"] == "g"
    assert body["quantity"] == 1500


def test_liter_scales_amount_on_consume(client):
    pid = client.post("/api/products", json={"name": "Milch", "default_unit": "ml"}).json()["id"]
    client.post("/api/stock", json={"product_id": pid, "quantity": 2000, "unit": "ml"})
    resp = client.post("/api/stock/consume", json={"product_id": pid, "amount": 1, "unit": "l"})
    assert resp.status_code == 200
    entries = client.get(f"/api/stock?product_id={pid}").json()
    items = entries["items"] if isinstance(entries, dict) else entries
    remaining = sum(e["quantity"] for e in items if e["product_id"] == pid)
    assert remaining == 1000


def test_kg_scales_min_stock_on_product_create(client):
    resp = client.post("/api/products", json={
        "name": "Kartoffeln", "default_unit": "g",
        "min_stock": 2, "min_stock_unit": "kg",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["min_stock"] == 2000
    assert body["min_stock_unit"] == "g"
