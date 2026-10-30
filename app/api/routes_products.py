"""Product routes: CRUD + search."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Product
from app.schemas import Page, ProductCreate, ProductOut, ProductUpdate
from app.services.products import ProductService

MAX_PAGE_LIMIT = 500

router = APIRouter(prefix="/api/products", tags=["products"])


# ----- helpers -----

def _product_out(p: Product) -> ProductOut:
    return ProductOut(
        id=p.id,
        name=p.name,
        barcode=p.barcode,
        category=p.category,
        default_unit=p.default_unit,
        nutrition_per_100=p.nutrition_per_100,
        typical_pack_sizes=p.typical_pack_sizes,
        shelf_life_type=p.shelf_life_type,
        shelf_life_days_default=p.shelf_life_days_default,
        image_url=p.image_url,
        synonyms=p.synonyms,
        min_stock=p.min_stock,
        min_stock_unit=p.min_stock_unit,
    )


# ----- routes -----

@router.get("", response_model=Page[ProductOut])
def list_products(
    q: str | None = None,
    category: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=MAX_PAGE_LIMIT),
    db: Session = Depends(get_db),
):
    svc = ProductService(db)
    if q:
        products, total = svc.search(q, offset=offset, limit=limit)
    else:
        products, total = svc.list_all(category=category, offset=offset, limit=limit)
    return Page[ProductOut](
        items=[_product_out(p) for p in products],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    svc = ProductService(db)
    product = svc.get(product_id)
    if not product:
        from app.domain import DomainError
        raise DomainError("Produkt nicht gefunden", {"product_id": product_id})
    return _product_out(product)


@router.post("", response_model=ProductOut, status_code=201)
def create_product(body: ProductCreate, db: Session = Depends(get_db)):
    svc = ProductService(db)
    product = svc.create(body)
    db.commit()
    db.refresh(product)
    return _product_out(product)


@router.put("/{product_id}", response_model=ProductOut)
def update_product(product_id: int, body: ProductUpdate, db: Session = Depends(get_db)):
    svc = ProductService(db)
    product = svc.update(product_id, body)
    db.commit()
    db.refresh(product)
    return _product_out(product)


@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    svc = ProductService(db)
    svc.delete(product_id)
    db.commit()
