from datetime import date, timedelta


def test_create_electronic_asset_auto_sell_candidate(client):
    resp = client.post("/api/electronics", json={
        "name": "ThinkPad USB-C Dock",
        "category": "Dockingstation",
        "brand": "Lenovo",
        "model": "40AS",
        "serial": "DOCK-001",
        "condition": "gut",
        "purchase_price": 15.0,
        "estimated_resale_value": 35.0,
        "desired_min_profit": 5.0,
        "ebay_watch_query": "Lenovo 40AS Dock",
        "external_refs": {"old_snipe_id": 123},
    })

    assert resp.status_code == 201
    data = resp.json()
    assert data["sell_decision"] == "verkaufen"
    assert data["estimated_profit"] == 20.0
    assert data["external_refs"]["old_snipe_id"] == 123

    candidates = client.get("/api/electronics/sell-candidates").json()
    assert len(candidates) == 1
    assert candidates[0]["decision"] == "verkaufen"


def test_active_bid_style_asset_can_be_kept_manually(client):
    resp = client.post("/api/electronics", json={
        "name": "Seltenes Ersatzteil",
        "condition": "sehr_gut",
        "purchase_price": 5.0,
        "estimated_resale_value": 50.0,
        "manual_pin": True,
        "sell_reason": "Noch nicht verkaufen, Teil wird eventuell gebraucht",
    })
    assert resp.status_code == 201
    assert resp.json()["sell_decision"] == "behalten"

    asset_id = resp.json()["id"]
    update = client.put(f"/api/electronics/{asset_id}", json={
        "sell_decision": "behalten",
        "sell_reason": "manuell behalten",
        "manual_pin": True,
    })
    assert update.status_code == 200
    assert update.json()["sell_decision"] == "behalten"
    assert update.json()["manual_pin"] is True


def test_expired_warranty_marks_asset_for_review(client):
    resp = client.post("/api/electronics", json={
        "name": "Alter Router",
        "purchase_price": 80.0,
        "estimated_resale_value": 60.0,
        "warranty_end": (date.today() - timedelta(days=1)).isoformat(),
    })

    assert resp.status_code == 201
    assert resp.json()["sell_decision"] == "pruefen"


def test_duplicate_serial_is_rejected(client):
    body = {"name": "Mini PC A", "serial": "SER-1"}
    assert client.post("/api/electronics", json=body).status_code == 201
    resp = client.post("/api/electronics", json={"name": "Mini PC B", "serial": "SER-1"})

    assert resp.status_code == 422


def test_homelab_active_asset_is_protected_from_sale(client):
    resp = client.post("/api/electronics", json={
        "name": "Intel NUC fuer Home Assistant",
        "category": "Homelab Host",
        "purchase_price": 100.0,
        "estimated_resale_value": 220.0,
        "usage_status": "critical",
        "homelab_role": "homeassistant",
        "host_name": "ha-node",
        "service_refs": ["homeassistant", "mqtt"],
    })

    assert resp.status_code == 201
    data = resp.json()
    assert data["sell_decision"] == "behalten"
    assert data["in_active_use"] is True
    assert data["service_refs"] == ["homeassistant", "mqtt"]
    assert "Aktiv in Verwendung" in data["sell_reason"]

    candidates = client.get("/api/electronics/sell-candidates").json()
    assert candidates == []


def test_electronics_search_by_name_brand_model(client):
    client.post("/api/electronics", json={"name": "ThinkPad X1", "brand": "Lenovo", "model": "X1C"})
    client.post("/api/electronics", json={"name": "Dell Optiplex", "brand": "Dell", "model": "7050"})
    client.post("/api/electronics", json={"name": "ThinkCentre", "brand": "Lenovo", "model": "M75"})

    page = client.get("/api/electronics?q=Lenovo").json()
    names = sorted(a["name"] for a in page["items"])
    assert names == ["ThinkCentre", "ThinkPad X1"]

    page = client.get("/api/electronics?q=7050").json()
    assert page["total"] == 1
    assert page["items"][0]["name"] == "Dell Optiplex"


def test_electronics_filter_combinations(client):
    client.post("/api/electronics", json={
        "name": "Router A", "category": "Netzwerk", "status": "aktiv", "sell_decision": "behalten",
    })
    client.post("/api/electronics", json={
        "name": "Router B", "category": "Netzwerk", "status": "ausgemustert",
        "purchase_price": 1.0, "estimated_resale_value": 50.0,
    })
    client.post("/api/electronics", json={
        "name": "USB-Stick", "category": "Storage", "status": "aktiv",
    })

    page = client.get("/api/electronics?category=Netzwerk&status=aktiv").json()
    assert page["total"] == 1
    assert page["items"][0]["name"] == "Router A"


def test_seed_known_homelab_assets(client):
    resp = client.post("/api/electronics/homelab/seed-known")

    assert resp.status_code == 200
    rows = resp.json()
    hosts = {row["host_name"]: row for row in rows}
    assert hosts["host"]["sell_decision"] == "behalten"
    assert hosts["host"]["manual_pin"] is True
    assert hosts["node1"]["in_active_use"] is True
