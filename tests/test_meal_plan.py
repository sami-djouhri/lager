"""Tests für /api/meal-plan + /api/recipes."""


def test_recipes_list_contains_bundled_templates(client):
    rows = client.get("/api/recipes").json()
    ids = {r["id"] for r in rows}
    assert "spaghetti-bolognese" in ids
    assert "reis-mit-gemuese" in ids


def test_meal_plan_unknown_recipe_returns_domain_error(client):
    resp = client.post("/api/meal-plan", json={"recipe_ids": ["does-not-exist"], "servings": 2})
    assert resp.status_code == 422
    assert "Rezept" in resp.json()["error"]


def test_meal_plan_unknown_ingredients_go_into_missing_stock(client):
    """Ohne Produkte im Katalog landen alle Rezept-Zutaten in missing_stock."""
    body = client.post("/api/meal-plan", json={
        "recipe_ids": ["reis-mit-gemuese"],
        "servings": 2,
    }).json()

    assert body["shopping_list"] == []
    names = {r["product_name"] for r in body["missing_stock"]}
    assert {"Reis", "Karotten", "Sojasauce"} <= names
    # 2 Portionen × 80g Reis = 160g
    reis = next(r for r in body["missing_stock"] if r["product_name"] == "Reis")
    assert reis["needed"] == 160
    assert reis["unit"] == "g"


def test_meal_plan_shopping_list_only_for_deficit(client):
    # Reis im Katalog mit reichlich Bestand → kein Shopping-Eintrag
    pid_reis = client.post("/api/products", json={"name": "Reis", "default_unit": "g"}).json()["id"]
    client.post("/api/stock", json={"product_id": pid_reis, "quantity": 500, "unit": "g"})

    # Karotten im Katalog, aber Bestand zu klein
    pid_karotten = client.post("/api/products", json={"name": "Karotten", "default_unit": "g"}).json()["id"]
    client.post("/api/stock", json={"product_id": pid_karotten, "quantity": 50, "unit": "g"})

    body = client.post("/api/meal-plan", json={
        "recipe_ids": ["reis-mit-gemuese"],
        "servings": 3,
    }).json()

    by_name = {r["product_name"]: r for r in body["shopping_list"]}
    # 3 × 80g Reis = 240g, vorhanden 500g → KEIN Eintrag
    assert "Reis" not in by_name
    # 3 × 100g Karotten = 300g, vorhanden 50g → missing 250g
    assert by_name["Karotten"]["missing"] == 250
    assert by_name["Karotten"]["unit"] == "g"

    missing_names = {r["product_name"] for r in body["missing_stock"]}
    assert "Sojasauce" in missing_names


def test_meal_plan_aggregates_across_recipes(client):
    """Zutaten aus mehreren Rezepten werden pro (name, unit) addiert."""
    pid = client.post("/api/products", json={"name": "Reis", "default_unit": "g"}).json()["id"]
    client.post("/api/stock", json={"product_id": pid, "quantity": 100, "unit": "g"})

    body = client.post("/api/meal-plan", json={
        "recipe_ids": ["reis-mit-gemuese", "reis-mit-gemuese"],
        "servings": 2,
    }).json()
    reis = next(r for r in body["shopping_list"] if r["product_name"] == "Reis")
    # 2 × (2 × 80g) = 320g, minus 100g Bestand = 220g
    assert reis["needed"] == 320
    assert reis["missing"] == 220
