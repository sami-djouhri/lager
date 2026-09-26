"""Tests für /api/shopping-list + /api/forecast."""

from datetime import date, timedelta


def _create_product(client, name: str, **kwargs) -> int:
    body = {"name": name, "default_unit": "g", **kwargs}
    return client.post("/api/products", json=body).json()["id"]


def test_shopping_list_low_stock_takes_priority(client):
    pid = _create_product(client, "Reis", min_stock=500, min_stock_unit="g")
    client.post("/api/stock", json={"product_id": pid, "quantity": 100, "unit": "g"})

    items = client.get("/api/shopping-list").json()
    assert len(items) == 1
    assert items[0]["product_id"] == pid
    assert items[0]["reason"] == "low_stock"
    assert items[0]["suggested_quantity"] == 400  # deficit
    assert items[0]["current_stock"] == 100


def test_shopping_list_expiring_soon(client):
    pid = _create_product(client, "Joghurt")
    soon = (date.today() + timedelta(days=3)).isoformat()
    client.post("/api/stock", json={
        "product_id": pid, "quantity": 200, "unit": "g", "mhd": soon,
    })

    items = client.get("/api/shopping-list").json()
    expiring = [i for i in items if i["reason"] == "expiring_soon"]
    assert expiring
    assert expiring[0]["product_id"] == pid


def test_shopping_list_low_stock_blocks_other_reasons(client):
    """low_stock muss expiring_soon-Hinweis fürs gleiche Produkt verdrängen."""
    pid = _create_product(client, "Milch", min_stock=1000, min_stock_unit="ml")
    soon = (date.today() + timedelta(days=2)).isoformat()
    client.post("/api/stock", json={
        "product_id": pid, "quantity": 500, "unit": "ml", "mhd": soon,
    })

    items = client.get("/api/shopping-list").json()
    matches = [i for i in items if i["product_id"] == pid]
    assert len(matches) == 1
    assert matches[0]["reason"] == "low_stock"


def test_forecast_expire_kind(client):
    pid = _create_product(client, "Käse")
    in_5 = (date.today() + timedelta(days=5)).isoformat()
    in_30 = (date.today() + timedelta(days=30)).isoformat()
    client.post("/api/stock", json={"product_id": pid, "quantity": 100, "unit": "g", "mhd": in_5})
    client.post("/api/stock", json={"product_id": pid, "quantity": 100, "unit": "g", "mhd": in_30})

    rows = client.get("/api/forecast?days=14&kind=expire").json()
    assert len(rows) == 1
    assert rows[0]["days_left"] == 5
    assert rows[0]["reason"] == "expire"


def test_forecast_unknown_kind_is_422(client):
    resp = client.get("/api/forecast?days=14&kind=bogus")
    assert resp.status_code == 422


def test_shopping_list_empty_when_no_products(client):
    assert client.get("/api/shopping-list").json() == []
