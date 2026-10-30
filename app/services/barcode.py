"""Barcode service: OpenFoodFacts lookup."""

from __future__ import annotations

import httpx

from app.config import settings
from app.logging import get_logger

logger = get_logger(__name__)


class BarcodeService:
    OPENFOODFACTS_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"

    async def lookup(self, barcode: str) -> dict | None:
        """Query OpenFoodFacts for product data.

        Returns a dict with name, category, nutrition, image_url or None.
        """
        url = self.OPENFOODFACTS_URL.format(barcode=barcode)
        try:
            async with httpx.AsyncClient(
                timeout=settings.OPENFOODFACTS_TIMEOUT_SEC
            ) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return None
                try:
                    data = resp.json()
                except (ValueError, TypeError) as exc:
                    logger.warning(
                        "openfoodfacts_json_parse_failed",
                        barcode=barcode,
                        error=str(exc),
                    )
                    return None
        except (httpx.TimeoutException, httpx.ConnectError):
            return None

        if data.get("status") != 1:
            return None

        product = data.get("product", {})
        name = (
            product.get("product_name_de")
            or product.get("product_name")
            or ""
        )
        if not name:
            return None

        nutrients = product.get("nutriments", {})
        nutrition = {
            "kcal": nutrients.get("energy-kcal_100g", 0),
            "protein_g": nutrients.get("proteins_100g", 0),
            "carbs_g": nutrients.get("carbohydrates_100g", 0),
            "fat_g": nutrients.get("fat_100g", 0),
            "fiber_g": nutrients.get("fiber_100g", 0),
        }

        category = product.get("categories_tags_de") or product.get("categories", "")
        if isinstance(category, list):
            category = category[0] if category else ""

        return {
            "barcode": barcode,
            "name": name.strip(),
            "category": category[:100] if category else None,
            "nutrition_per_100": nutrition,
            "image_url": product.get("image_url"),
        }
