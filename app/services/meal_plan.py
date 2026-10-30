"""Meal-Plan-Service: liest JSON-Rezept-Templates und berechnet Zutaten-Aggregation."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain import normalise_amount
from app.models import Product, StockEntry

RECIPES_DIR = Path(__file__).resolve().parent.parent / "data" / "recipes"


@dataclass
class Recipe:
    id: str
    name: str
    servings_default: int
    ingredients: list[dict]


class RecipeNotFoundError(LookupError):
    pass


def list_recipes() -> list[Recipe]:
    if not RECIPES_DIR.is_dir():
        return []
    out: list[Recipe] = []
    for path in sorted(RECIPES_DIR.glob("*.json")):
        out.append(_load(path))
    return out


def get_recipe(recipe_id: str) -> Recipe:
    path = RECIPES_DIR / f"{recipe_id}.json"
    if not path.is_file():
        raise RecipeNotFoundError(recipe_id)
    return _load(path)


def _load(path: Path) -> Recipe:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Recipe(
        id=data["id"],
        name=data["name"],
        servings_default=int(data.get("servings_default", 1)),
        ingredients=list(data.get("ingredients", [])),
    )


def plan(
    db: Session,
    *,
    recipe_ids: list[str],
    servings: int,
) -> dict:
    """Berechnet kumulierten Zutatenbedarf vs. Bestand.

    Output:
      requested:        Liste der ausgewählten Rezepte mit Portionen
      shopping_list:    Produkte, deren Bestand < Bedarf (positive missing)
      missing_stock:    Zutaten, die im Produktkatalog fehlen
    """
    if servings <= 0:
        raise ValueError("servings must be > 0")

    requested = []
    needed: dict[tuple[str, str], float] = defaultdict(float)  # (lower_name, unit) -> amount
    for rid in recipe_ids:
        recipe = get_recipe(rid)
        requested.append({
            "recipe_id": recipe.id,
            "name": recipe.name,
            "servings": servings,
        })
        for ing in recipe.ingredients:
            amount, unit = normalise_amount(float(ing["amount_per_serving"]), ing["unit"])
            key = (ing["product_name"].strip().lower(), unit)
            needed[key] += amount * servings

    # Resolve product_name → product_id + check current stock
    name_to_product = _resolve_products(db, [k[0] for k in needed.keys()])
    totals = _totals_by_product(db)

    shopping_list: list[dict] = []
    missing_stock: list[dict] = []
    for (name_lower, unit), required in needed.items():
        product = name_to_product.get(name_lower)
        if product is None:
            # Original-Schreibweise aus dem letzten Rezept rekonstruieren:
            original = next(
                ing["product_name"]
                for rid in recipe_ids
                for ing in get_recipe(rid).ingredients
                if ing["product_name"].strip().lower() == name_lower
            )
            missing_stock.append({
                "product_id": None,
                "product_name": original,
                "needed": round(required, 2),
                "unit": unit,
            })
            continue
        available = totals.get((product.id, unit), 0.0)
        missing = required - available
        if missing > 0.001:
            shopping_list.append({
                "product_id": product.id,
                "product_name": product.name,
                "needed": round(required, 2),
                "available": round(available, 2),
                "missing": round(missing, 2),
                "unit": unit,
            })

    shopping_list.sort(key=lambda r: r["product_name"].lower())
    missing_stock.sort(key=lambda r: r["product_name"].lower())
    return {
        "requested": requested,
        "shopping_list": shopping_list,
        "missing_stock": missing_stock,
    }


def _resolve_products(db: Session, lower_names: list[str]) -> dict[str, Product]:
    if not lower_names:
        return {}
    stmt = select(Product).where(func.lower(Product.name).in_(set(lower_names)))
    result: dict[str, Product] = {}
    for p in db.execute(stmt).scalars().all():
        result[p.name.lower()] = p
    return result


def _totals_by_product(db: Session) -> dict[tuple[int, str], float]:
    stmt = (
        select(
            StockEntry.product_id,
            StockEntry.unit,
            func.sum(StockEntry.quantity).label("total"),
        )
        .where(StockEntry.quantity > 0)
        .group_by(StockEntry.product_id, StockEntry.unit)
    )
    return {(r.product_id, r.unit): float(r.total) for r in db.execute(stmt).all()}
