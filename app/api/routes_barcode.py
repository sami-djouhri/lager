"""Barcode routes: lookup by EAN/UPC."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import ProductOut
from app.services.barcode import BarcodeService
from app.services.products import ProductService

router = APIRouter(prefix="/api/barcode", tags=["barcode"])


@router.get("/{code}")
async def lookup_barcode(code: str, db: Session = Depends(get_db)):
    # First: check if product with this barcode already exists in DB
    psvc = ProductService(db)
    existing = psvc.get_by_barcode(code)
    if existing:
        return {
            "source": "db",
            "product": ProductOut(
                id=existing.id,
                name=existing.name,
                barcode=existing.barcode,
                category=existing.category,
                default_unit=existing.default_unit,
                nutrition_per_100=existing.nutrition_per_100,
                typical_pack_sizes=existing.typical_pack_sizes,
                shelf_life_type=existing.shelf_life_type,
                shelf_life_days_default=existing.shelf_life_days_default,
                image_url=existing.image_url,
                synonyms=existing.synonyms,
            ).model_dump(),
        }

    # Second: query OpenFoodFacts
    bsvc = BarcodeService()
    result = await bsvc.lookup(code)
    if result:
        return {"source": "openfoodfacts", "product": result}

    return {"source": None, "product": None}
