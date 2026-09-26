"""Tests for FIFO consumption logic."""

from datetime import date, timedelta


def _setup_product(client, name="Reis"):
    resp = client.post("/api/products", json={"name": name, "default_unit": "g"})
    return resp.json()["id"]


def _add_stock(client, product_id, quantity, unit="g", mhd=None):
    body = {"product_id": product_id, "quantity": quantity, "unit": unit}
    if mhd:
        body["mhd"] = mhd
    resp = client.post("/api/stock", json=body)
    return resp.json()["id"]


def test_fifo_oldest_mhd_first(client):
    """Consumption should use the oldest MHD first."""
    pid = _setup_product(client)
    today = date.today()

    # Entry A: expires in 3 days (should be consumed first)
    _add_stock(client, pid, 200, mhd=(today + timedelta(days=3)).isoformat())
    # Entry B: expires in 30 days
    _add_stock(client, pid, 300, mhd=(today + timedelta(days=30)).isoformat())

    resp = client.post("/api/stock/consume", json={
        "product_id": pid, "amount": 150, "unit": "g"
    })
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 1
    assert events[0]["amount"] == 150

    # Check remaining stock: Entry A should have 50g left, Entry B still 300g
    resp = client.get(f"/api/stock?product_id={pid}")
    entries = sorted(resp.json()["items"], key=lambda e: e["quantity"])
    assert entries[0]["quantity"] == 50
    assert entries[1]["quantity"] == 300


def test_fifo_across_multiple_entries(client):
    """Consumption spanning multiple entries."""
    pid = _setup_product(client)
    today = date.today()

    _add_stock(client, pid, 100, mhd=(today + timedelta(days=3)).isoformat())
    _add_stock(client, pid, 200, mhd=(today + timedelta(days=10)).isoformat())

    resp = client.post("/api/stock/consume", json={
        "product_id": pid, "amount": 250, "unit": "g"
    })
    assert resp.status_code == 200
    events = resp.json()
    # Should create 2 events: 100 from first entry, 150 from second
    assert len(events) == 2
    amounts = sorted([e["amount"] for e in events])
    assert amounts == [100, 150]


def test_fifo_insufficient_stock(client):
    """Consuming more than available raises an error."""
    pid = _setup_product(client)
    _add_stock(client, pid, 100)

    resp = client.post("/api/stock/consume", json={
        "product_id": pid, "amount": 200, "unit": "g"
    })
    assert resp.status_code == 422
    assert "Nicht genug" in resp.json()["error"]


def test_fifo_no_stock(client):
    """Consuming from a product with no stock raises an error."""
    pid = _setup_product(client)

    resp = client.post("/api/stock/consume", json={
        "product_id": pid, "amount": 100, "unit": "g"
    })
    assert resp.status_code == 422
    assert "Kein Bestand" in resp.json()["error"]


def test_fifo_null_mhd_last(client):
    """Entries without MHD should be consumed last."""
    pid = _setup_product(client)
    today = date.today()

    # Entry A: no MHD (should be consumed last)
    _add_stock(client, pid, 200)
    # Entry B: expires in 5 days (should be consumed first)
    _add_stock(client, pid, 200, mhd=(today + timedelta(days=5)).isoformat())

    resp = client.post("/api/stock/consume", json={
        "product_id": pid, "amount": 150, "unit": "g"
    })
    events = resp.json()
    assert len(events) == 1

    # The entry with MHD should have been consumed first → 50g left
    # The entry without MHD should still have 200g
    resp = client.get(f"/api/stock?product_id={pid}")
    entries = sorted(resp.json()["items"], key=lambda e: e["quantity"])
    assert entries[0]["quantity"] == 50  # MHD entry partially consumed
    assert entries[1]["quantity"] == 200  # null-MHD entry untouched


def test_consume_for_recipe_atomic(client):
    """Recipe consumption: all-or-nothing."""
    pid1 = _setup_product(client, "Reis")
    pid2 = _setup_product(client, "Butter")

    _add_stock(client, pid1, 500, "g")
    _add_stock(client, pid2, 50, "g")  # Only 50g available

    # Try to consume 200g Reis + 100g Butter → Butter insufficient
    resp = client.post("/api/stock/consume-recipe", json={
        "ingredients": [
            {"product_id": pid1, "amount": 200, "unit": "g"},
            {"product_id": pid2, "amount": 100, "unit": "g"},
        ]
    })
    assert resp.status_code == 422
    assert "Zutaten fehlen" in resp.json()["error"]

    # Verify nothing was consumed (atomic rollback)
    resp = client.get(f"/api/stock/available?product_id={pid1}&unit=g")
    assert resp.json()["total"] == 500


def test_consume_for_recipe_success(client):
    """Successful recipe consumption."""
    pid1 = _setup_product(client, "Reis")
    pid2 = _setup_product(client, "Butter")

    _add_stock(client, pid1, 500, "g")
    _add_stock(client, pid2, 200, "g")

    resp = client.post("/api/stock/consume-recipe", json={
        "ingredients": [
            {"product_id": pid1, "amount": 200, "unit": "g"},
            {"product_id": pid2, "amount": 50, "unit": "g"},
        ]
    })
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 2

    # Verify remaining stock
    resp1 = client.get(f"/api/stock/available?product_id={pid1}&unit=g")
    assert resp1.json()["total"] == 300

    resp2 = client.get(f"/api/stock/available?product_id={pid2}&unit=g")
    assert resp2.json()["total"] == 150


def test_consume_reason_and_source(client):
    """Verify reason and source are stored."""
    pid = _setup_product(client)
    _add_stock(client, pid, 500, "g")

    resp = client.post("/api/stock/consume", json={
        "product_id": pid,
        "amount": 100,
        "unit": "g",
        "reason": "weggeworfen",
        "source": "manual",
    })
    assert resp.status_code == 200
    event = resp.json()[0]
    assert event["reason"] == "weggeworfen"
    assert event["source"] == "manual"
