"""Tests for pagination on list endpoints (offset/limit + Page[T] wrapper)."""


def _create_product(client, name: str) -> int:
    resp = client.post("/api/products", json={"name": name, "default_unit": "g"})
    assert resp.status_code == 201
    return resp.json()["id"]


def test_products_default_pagination(client):
    for i in range(5):
        _create_product(client, f"Prod {i}")

    resp = client.get("/api/products")
    page = resp.json()
    assert page["total"] == 5
    assert page["offset"] == 0
    assert page["limit"] == 200
    assert len(page["items"]) == 5


def test_products_offset_limit(client):
    for i in range(10):
        _create_product(client, f"P{i:02d}")

    page = client.get("/api/products?offset=3&limit=4").json()
    assert page["total"] == 10
    assert page["offset"] == 3
    assert page["limit"] == 4
    assert len(page["items"]) == 4
    # Products are sorted by name → P03..P06 expected
    names = [p["name"] for p in page["items"]]
    assert names == ["P03", "P04", "P05", "P06"]


def test_products_offset_beyond_total(client):
    _create_product(client, "Solo")
    page = client.get("/api/products?offset=10&limit=5").json()
    assert page["total"] == 1
    assert page["items"] == []


def test_stock_pagination(client):
    pid = _create_product(client, "Reis")
    for q in (100, 200, 300, 400, 500):
        client.post("/api/stock", json={"product_id": pid, "quantity": q, "unit": "g"})

    page = client.get("/api/stock?limit=2").json()
    assert page["total"] == 5
    assert len(page["items"]) == 2


def test_electronics_pagination(client):
    for i in range(7):
        client.post("/api/electronics", json={"name": f"Asset {i}", "serial": f"S{i}"})

    page = client.get("/api/electronics?offset=2&limit=3").json()
    assert page["total"] == 7
    assert page["offset"] == 2
    assert page["limit"] == 3
    assert len(page["items"]) == 3


def test_pagination_limit_validation(client):
    # limit=0 → 422
    resp = client.get("/api/products?limit=0")
    assert resp.status_code == 422
    # limit > MAX (500) → 422
    resp = client.get("/api/products?limit=501")
    assert resp.status_code == 422
    # offset negative → 422
    resp = client.get("/api/products?offset=-1")
    assert resp.status_code == 422


def test_stock_low_stock_route_removed(client):
    """Duplikat /api/stock/low-stock entfernt; canonical ist /api/stats/low-stock."""
    # Vorher matchte hier eine eigene Route mit list[LowStockItem]-Response.
    # Jetzt fällt der Pfad in /api/stock/{entry_id:int} → FastAPI antwortet 422
    # (Pfadparameter „low-stock“ ist keine int). Das beweist: keine eigene Route mehr.
    resp = client.get("/api/stock/low-stock")
    assert resp.status_code == 422
    canonical = client.get("/api/stats/low-stock")
    assert canonical.status_code == 200
