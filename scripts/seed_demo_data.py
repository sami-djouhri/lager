"""Seed demo products and stock entries. Only runs if DB is empty."""

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.db import SessionLocal
from app.models import ConsumptionEvent, Product, StockEntry


def seed():
    db = SessionLocal()
    try:
        existing = db.execute(select(Product).limit(1)).scalar_one_or_none()
        if existing:
            print("DB already seeded, skipping.")
            return

        today = date.today()

        products_data = [
            {
                "name": "Reis",
                "category": "Getreide",
                "default_unit": "g",
                "barcode": "4006381333627",
                "synonyms_json": '["Basmati", "Langkorn"]',
                "shelf_life_days_default": 365,
                "nutrition_per_100_json": '{"kcal": 349, "protein_g": 7.0, "carbs_g": 78.0, "fat_g": 0.6, "fiber_g": 1.4}',
            },
            {
                "name": "Nudeln",
                "category": "Getreide",
                "default_unit": "g",
                "barcode": "4002221037564",
                "synonyms_json": '["Spaghetti", "Penne", "Pasta"]',
                "shelf_life_days_default": 730,
                "nutrition_per_100_json": '{"kcal": 353, "protein_g": 12.0, "carbs_g": 72.0, "fat_g": 1.5, "fiber_g": 3.0}',
            },
            {
                "name": "Tomaten (Dose)",
                "category": "Konserven",
                "default_unit": "g",
                "synonyms_json": '["Dosentomaten", "Pelati", "Passata"]',
                "shelf_life_days_default": 365,
                "nutrition_per_100_json": '{"kcal": 22, "protein_g": 1.0, "carbs_g": 3.5, "fat_g": 0.1, "fiber_g": 1.0}',
            },
            {
                "name": "Milch",
                "category": "Milchprodukte",
                "default_unit": "ml",
                "shelf_life_days_default": 10,
                "nutrition_per_100_json": '{"kcal": 64, "protein_g": 3.4, "carbs_g": 4.8, "fat_g": 3.5, "fiber_g": 0}',
            },
            {
                "name": "Eier",
                "category": "Eier",
                "default_unit": "piece",
                "shelf_life_days_default": 28,
                "nutrition_per_100_json": '{"kcal": 155, "protein_g": 13.0, "carbs_g": 1.1, "fat_g": 11.0, "fiber_g": 0}',
            },
            {
                "name": "Haehnchenbrust",
                "category": "Fleisch",
                "default_unit": "g",
                "shelf_life_type": "Verbrauchsdatum",
                "shelf_life_days_default": 5,
                "nutrition_per_100_json": '{"kcal": 165, "protein_g": 31.0, "carbs_g": 0, "fat_g": 3.6, "fiber_g": 0}',
            },
            {
                "name": "Brokkoli",
                "category": "Gemuese",
                "default_unit": "g",
                "shelf_life_days_default": 7,
                "nutrition_per_100_json": '{"kcal": 34, "protein_g": 2.8, "carbs_g": 7.0, "fat_g": 0.4, "fiber_g": 2.6}',
            },
            {
                "name": "Zwiebeln",
                "category": "Gemuese",
                "default_unit": "g",
                "shelf_life_days_default": 30,
                "nutrition_per_100_json": '{"kcal": 40, "protein_g": 1.1, "carbs_g": 9.3, "fat_g": 0.1, "fiber_g": 1.7}',
            },
            {
                "name": "Knoblauch",
                "category": "Gemuese",
                "default_unit": "g",
                "shelf_life_days_default": 60,
                "nutrition_per_100_json": '{"kcal": 149, "protein_g": 6.4, "carbs_g": 33.0, "fat_g": 0.5, "fiber_g": 2.1}',
            },
            {
                "name": "Olivenoel",
                "category": "Oele",
                "default_unit": "ml",
                "shelf_life_days_default": 540,
                "nutrition_per_100_json": '{"kcal": 884, "protein_g": 0, "carbs_g": 0, "fat_g": 100, "fiber_g": 0}',
            },
            {
                "name": "Butter",
                "category": "Milchprodukte",
                "default_unit": "g",
                "shelf_life_days_default": 90,
                "nutrition_per_100_json": '{"kcal": 717, "protein_g": 0.9, "carbs_g": 0.1, "fat_g": 81.0, "fiber_g": 0}',
            },
            {
                "name": "Mehl",
                "category": "Getreide",
                "default_unit": "g",
                "synonyms_json": '["Weizenmehl", "Type 405"]',
                "shelf_life_days_default": 365,
                "nutrition_per_100_json": '{"kcal": 364, "protein_g": 10.0, "carbs_g": 76.0, "fat_g": 1.0, "fiber_g": 2.7}',
            },
            {
                "name": "Zucker",
                "category": "Gewuerze",
                "default_unit": "g",
                "shelf_life_days_default": 1825,
                "nutrition_per_100_json": '{"kcal": 400, "protein_g": 0, "carbs_g": 100, "fat_g": 0, "fiber_g": 0}',
            },
            {
                "name": "Salz",
                "category": "Gewuerze",
                "default_unit": "g",
                "shelf_life_days_default": 3650,
                "nutrition_per_100_json": '{"kcal": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "fiber_g": 0}',
            },
            {
                "name": "Paprika",
                "category": "Gemuese",
                "default_unit": "g",
                "shelf_life_days_default": 10,
                "nutrition_per_100_json": '{"kcal": 31, "protein_g": 1.0, "carbs_g": 6.0, "fat_g": 0.3, "fiber_g": 2.1}',
            },
            {
                "name": "Kartoffeln",
                "category": "Gemuese",
                "default_unit": "g",
                "shelf_life_days_default": 30,
                "nutrition_per_100_json": '{"kcal": 77, "protein_g": 2.0, "carbs_g": 17.0, "fat_g": 0.1, "fiber_g": 2.2}',
            },
            {
                "name": "Karotten",
                "category": "Gemuese",
                "default_unit": "g",
                "synonyms_json": '["Moehren", "Mohrueben"]',
                "shelf_life_days_default": 21,
                "nutrition_per_100_json": '{"kcal": 41, "protein_g": 0.9, "carbs_g": 10.0, "fat_g": 0.2, "fiber_g": 2.8}',
            },
            {
                "name": "Kaese",
                "category": "Milchprodukte",
                "default_unit": "g",
                "synonyms_json": '["Gouda", "Emmentaler"]',
                "shelf_life_days_default": 30,
                "nutrition_per_100_json": '{"kcal": 356, "protein_g": 25.0, "carbs_g": 2.2, "fat_g": 27.0, "fiber_g": 0}',
            },
            {
                "name": "Joghurt",
                "category": "Milchprodukte",
                "default_unit": "g",
                "shelf_life_days_default": 14,
                "nutrition_per_100_json": '{"kcal": 61, "protein_g": 3.5, "carbs_g": 4.7, "fat_g": 3.2, "fiber_g": 0}',
            },
            {
                "name": "Haferflocken",
                "category": "Getreide",
                "default_unit": "g",
                "shelf_life_days_default": 365,
                "nutrition_per_100_json": '{"kcal": 372, "protein_g": 13.0, "carbs_g": 59.0, "fat_g": 7.0, "fiber_g": 10.0}',
            },
        ]

        products = []
        for pd in products_data:
            p = Product(**pd)
            db.add(p)
            products.append(p)
        db.flush()

        # Stock entries with varied MHD
        stock_configs = [
            # (product_index, quantity, unit, mhd_offset_days, location)
            (0, 1000, "g", 180, "Vorratskammer"),
            (0, 500, "g", 30, "Vorratskammer"),
            (1, 500, "g", 365, "Vorratskammer"),
            (1, 500, "g", 5, "Vorratskammer"),  # bald ablaufend
            (2, 400, "g", 200, "Vorratskammer"),
            (2, 400, "g", -3, "Vorratskammer"),  # abgelaufen
            (3, 1000, "ml", 8, "Kuehlschrank"),
            (3, 1000, "ml", 2, "Kuehlschrank"),  # kritisch
            (4, 10, "piece", 14, "Kuehlschrank"),
            (5, 400, "g", 3, "Kuehlschrank"),  # kritisch
            (6, 300, "g", 5, "Kuehlschrank"),
            (7, 500, "g", 20, "Vorratskammer"),
            (8, 100, "g", 45, "Vorratskammer"),
            (9, 750, "ml", 300, "Vorratskammer"),
            (10, 250, "g", 60, "Kuehlschrank"),
            (11, 1000, "g", 200, "Vorratskammer"),
            (12, 500, "g", 500, "Vorratskammer"),
            (13, 500, "g", 1000, "Vorratskammer"),
            (14, 200, "g", 6, "Kuehlschrank"),
            (15, 2000, "g", 25, "Vorratskammer"),
            (16, 500, "g", 10, "Kuehlschrank"),
            (17, 200, "g", 15, "Kuehlschrank"),
            (18, 500, "g", 7, "Kuehlschrank"),
            (19, 500, "g", 180, "Vorratskammer"),
        ]

        entries = []
        for idx, qty, unit, mhd_off, loc in stock_configs:
            entry = StockEntry(
                product_id=products[idx].id,
                quantity=qty,
                unit=unit,
                mhd=today + timedelta(days=mhd_off),
                purchase_date=today - timedelta(days=max(0, 30 - mhd_off)),
                location=loc,
            )
            db.add(entry)
            entries.append(entry)
        db.flush()

        # Sample consumption events
        consumption_data = [
            # (entry_index, amount, unit, reason, days_ago)
            (0, 200, "g", "verbraucht", 5),
            (0, 100, "g", "verbraucht", 2),
            (2, 250, "g", "verbraucht", 7),
            (6, 250, "ml", "verbraucht", 3),
            (8, 2, "piece", "verbraucht", 1),
            (5, 100, "g", "weggeworfen", 10),  # waste
        ]

        for eidx, amount, unit, reason, days_ago in consumption_data:
            event = ConsumptionEvent(
                stock_entry_id=entries[eidx].id,
                amount=amount,
                unit=unit,
                reason=reason,
                source="manual",
                consumed_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
            )
            db.add(event)

        db.commit()
        print(f"Seeded {len(products)} products, {len(entries)} stock entries, "
              f"{len(consumption_data)} consumption events.")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
