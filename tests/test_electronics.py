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


def test_alter_aktiver_usage_status_wird_im_einsatz_und_schuetzt(client):
    # Alte Form (vor Stufe 3): usage_status critical. Homelab-Felder werden ignoriert.
    resp = client.post("/api/electronics", json={
        "name": "Intel NUC fuer Home Assistant",
        "category": "Mini-PC",
        "purchase_price": 100.0,
        "estimated_resale_value": 220.0,
        "usage_status": "critical",
        "host_name": "ha-node",
    })

    assert resp.status_code == 201
    data = resp.json()
    assert data["sell_decision"] == "behalten"
    assert data["in_active_use"] is True
    assert data["verbleib"] == "shopfloor"
    assert data["shopfloor_grund"] == "im_einsatz"
    assert data["usage_status"] == "daily_use"
    assert "host_name" not in data
    assert data["sell_reason"] == "Im Einsatz"

    candidates = client.get("/api/electronics/sell-candidates").json()
    assert candidates == []


def test_zurueck_an_den_platz_hebt_den_schutz_auf(client):
    raum = client.post("/api/plaetze", json={"name": "Keller", "art": "raum"}).json()
    sid = client.post("/api/electronics", json={
        "name": "Laptop", "shopfloor_grund": "im_einsatz", "platz_id": raum["id"],
    }).json()["id"]
    resp = client.put(f"/api/electronics/{sid}", json={"verbleib": "eingelagert"})
    assert resp.status_code == 200
    d = resp.json()
    assert d["verbleib"] == "eingelagert"
    assert d["shopfloor_grund"] is None
    assert d["in_active_use"] is False
    assert d["location"] == "Keller"
    assert d["platz_kennung"] == "L-001"


def test_einlagern_ohne_platz_wird_abgelehnt(client):
    sid = client.post("/api/electronics", json={"name": "Kamera"}).json()["id"]
    resp = client.put(f"/api/electronics/{sid}", json={"verbleib": "eingelagert"})
    assert resp.status_code == 422


def test_verliehen_gibt_es_erst_mit_stufe_7(client):
    sid = client.post("/api/electronics", json={"name": "Bohrer"}).json()["id"]
    resp = client.put(f"/api/electronics/{sid}", json={"verbleib": "verliehen"})
    assert resp.status_code == 422


def test_platz_zuweisen_lagert_ein(client):
    raum = client.post("/api/plaetze", json={"name": "Arbeitszimmer", "art": "raum"}).json()
    sid = client.post("/api/electronics", json={"name": "Monitor"}).json()["id"]
    d = client.put(f"/api/electronics/{sid}", json={"platz_id": raum["id"]}).json()
    assert d["verbleib"] == "eingelagert"
    # Und zurueck auf den Shopfloor mit Grund: der Platz bleibt stehen.
    d = client.put(f"/api/electronics/{sid}", json={"shopfloor_grund": "reparatur"}).json()
    assert d["verbleib"] == "shopfloor"
    assert d["platz_id"] == raum["id"]
    # Platz und ausdruecklich „noch nicht eingelagert": bleibt auf dem Shopfloor.
    d = client.put(f"/api/electronics/{sid}", json={"platz_id": raum["id"],
                                                     "shopfloor_grund": None}).json()
    assert (d["verbleib"], d["shopfloor_grund"]) == ("shopfloor", None)


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


