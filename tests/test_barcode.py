"""Tests for barcode lookup."""

from unittest.mock import AsyncMock, patch


def test_barcode_from_db(client):
    """Known barcode returns product from DB."""
    client.post("/api/products", json={
        "name": "Reis", "barcode": "4006381333627", "default_unit": "g"
    })

    resp = client.get("/api/barcode/4006381333627")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "db"
    assert data["product"]["name"] == "Reis"


def test_barcode_from_openfoodfacts(client):
    """Unknown barcode queries OpenFoodFacts."""
    mock_result = {
        "barcode": "1234567890123",
        "name": "Testprodukt",
        "category": "Snacks",
        "nutrition_per_100": {"kcal": 200, "protein_g": 5, "carbs_g": 30, "fat_g": 8, "fiber_g": 2},
        "image_url": "https://example.com/img.jpg",
    }

    with patch(
        "app.api.routes_barcode.BarcodeService.lookup",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        resp = client.get("/api/barcode/1234567890123")
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "openfoodfacts"
        assert data["product"]["name"] == "Testprodukt"


def test_barcode_not_found(client):
    """Unknown barcode, OpenFoodFacts returns nothing."""
    with patch(
        "app.api.routes_barcode.BarcodeService.lookup",
        new_callable=AsyncMock,
        return_value=None,
    ):
        resp = client.get("/api/barcode/0000000000000")
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] is None
        assert data["product"] is None
