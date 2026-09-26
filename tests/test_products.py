"""Tests for product CRUD and search."""


def _create_product(client, name="Reis", **kwargs):
    body = {"name": name, "category": "Getreide", "default_unit": "g", **kwargs}
    return client.post("/api/products", json=body)


def test_create_and_list(client):
    resp = _create_product(client)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Reis"
    assert data["id"] > 0

    resp = client.get("/api/products")
    assert resp.status_code == 200
    page = resp.json()
    assert page["total"] == 1
    assert len(page["items"]) == 1


def test_get_by_id(client):
    create_resp = _create_product(client)
    pid = create_resp.json()["id"]

    resp = client.get(f"/api/products/{pid}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Reis"


def test_get_not_found(client):
    resp = client.get("/api/products/999")
    assert resp.status_code == 422


def test_update(client):
    create_resp = _create_product(client)
    pid = create_resp.json()["id"]

    resp = client.put(f"/api/products/{pid}", json={"category": "Beilage"})
    assert resp.status_code == 200
    assert resp.json()["category"] == "Beilage"


def test_delete(client):
    create_resp = _create_product(client)
    pid = create_resp.json()["id"]

    resp = client.delete(f"/api/products/{pid}")
    assert resp.status_code == 204

    resp = client.get("/api/products")
    assert resp.json()["total"] == 0


def test_delete_with_stock_fails(client, db_session):
    create_resp = _create_product(client)
    pid = create_resp.json()["id"]

    # Add stock entry
    client.post("/api/stock", json={
        "product_id": pid, "quantity": 100, "unit": "g"
    })

    resp = client.delete(f"/api/products/{pid}")
    assert resp.status_code == 422
    assert "Bestand" in resp.json()["error"]


def test_duplicate_name_fails(client):
    _create_product(client, name="Reis")
    resp = _create_product(client, name="Reis")
    assert resp.status_code == 422
    assert "existiert" in resp.json()["error"]


def test_search(client):
    _create_product(client, name="Reis")
    _create_product(client, name="Nudeln")
    _create_product(client, name="Risotto-Reis", category="Reis")

    resp = client.get("/api/products?q=Reis")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()["items"]]
    assert "Reis" in names
    assert "Risotto-Reis" in names
    assert "Nudeln" not in names


def test_filter_by_category(client):
    _create_product(client, name="Reis", category="Getreide")
    _create_product(client, name="Milch", category="Milchprodukte")

    resp = client.get("/api/products?category=Getreide")
    assert resp.status_code == 200
    page = resp.json()
    assert page["total"] == 1
    assert page["items"][0]["name"] == "Reis"


def test_barcode_uniqueness(client):
    _create_product(client, name="Reis", barcode="123456")
    resp = _create_product(client, name="Nudeln", barcode="123456")
    assert resp.status_code == 422
    assert "Barcode" in resp.json()["error"]


def test_nutrition_and_synonyms(client):
    resp = _create_product(
        client,
        name="Reis",
        nutrition_per_100={"kcal": 349, "protein_g": 7, "carbs_g": 78, "fat_g": 0.6, "fiber_g": 1.4},
        synonyms=["Basmati", "Langkorn"],
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["nutrition_per_100"]["kcal"] == 349
    assert "Basmati" in data["synonyms"]
