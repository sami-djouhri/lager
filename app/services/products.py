"""Product service: CRUD + search."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.domain import DomainError
from app.models import Product, StockEntry
from app.schemas import ProductCreate, ProductUpdate


class ProductService:
    def __init__(self, db: Session):
        self.db = db

    def list_all(
        self,
        category: str | None = None,
        offset: int = 0,
        limit: int = 200,
    ) -> tuple[list[Product], int]:
        stmt = select(Product)
        if category:
            stmt = stmt.where(Product.category == category)
        stmt = stmt.order_by(Product.name)
        rows = list(self.db.execute(stmt).scalars().all())
        return rows[offset : offset + limit], len(rows)

    def search(
        self,
        q: str,
        offset: int = 0,
        limit: int = 200,
    ) -> tuple[list[Product], int]:
        pattern = f"%{q}%"
        stmt = (
            select(Product)
            .where(
                or_(
                    Product.name.ilike(pattern),
                    Product.synonyms_json.ilike(pattern),
                )
            )
            .order_by(Product.name)
        )
        rows = list(self.db.execute(stmt).scalars().all())
        return rows[offset : offset + limit], len(rows)

    def get(self, product_id: int) -> Product | None:
        return self.db.get(Product, product_id)

    def get_by_barcode(self, barcode: str) -> Product | None:
        stmt = select(Product).where(Product.barcode == barcode)
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, data: ProductCreate) -> Product:
        existing = self.db.execute(
            select(Product).where(Product.name == data.name)
        ).scalar_one_or_none()
        if existing:
            raise DomainError(
                f"Produkt '{data.name}' existiert bereits",
                {"existing_id": existing.id},
            )
        if data.barcode:
            bc_existing = self.get_by_barcode(data.barcode)
            if bc_existing:
                raise DomainError(
                    f"Barcode '{data.barcode}' bereits vergeben an '{bc_existing.name}'",
                    {"existing_id": bc_existing.id},
                )

        product = Product(
            name=data.name,
            barcode=data.barcode,
            category=data.category,
            default_unit=data.default_unit,
            shelf_life_type=data.shelf_life_type,
            shelf_life_days_default=data.shelf_life_days_default,
            image_url=data.image_url,
            min_stock=data.min_stock,
            min_stock_unit=data.min_stock_unit,
        )
        if data.nutrition_per_100:
            product.nutrition_per_100 = data.nutrition_per_100.model_dump()
        product.typical_pack_sizes = data.typical_pack_sizes
        product.synonyms = data.synonyms
        self.db.add(product)
        self.db.flush()
        return product

    def update(self, product_id: int, data: ProductUpdate) -> Product:
        product = self.get(product_id)
        if not product:
            raise DomainError("Produkt nicht gefunden", {"product_id": product_id})

        if data.name is not None and data.name != product.name:
            existing = self.db.execute(
                select(Product).where(Product.name == data.name)
            ).scalar_one_or_none()
            if existing:
                raise DomainError(
                    f"Produkt '{data.name}' existiert bereits",
                    {"existing_id": existing.id},
                )
            product.name = data.name

        if data.barcode is not None and data.barcode != product.barcode:
            if data.barcode:
                bc_existing = self.get_by_barcode(data.barcode)
                if bc_existing and bc_existing.id != product_id:
                    raise DomainError(
                        f"Barcode '{data.barcode}' bereits vergeben",
                        {"existing_id": bc_existing.id},
                    )
            product.barcode = data.barcode

        if data.category is not None:
            product.category = data.category
        if data.default_unit is not None:
            product.default_unit = data.default_unit
        if data.nutrition_per_100 is not None:
            product.nutrition_per_100 = data.nutrition_per_100.model_dump()
        if data.typical_pack_sizes is not None:
            product.typical_pack_sizes = data.typical_pack_sizes
        if data.shelf_life_type is not None:
            product.shelf_life_type = data.shelf_life_type
        if data.shelf_life_days_default is not None:
            product.shelf_life_days_default = data.shelf_life_days_default
        if data.image_url is not None:
            product.image_url = data.image_url
        if data.synonyms is not None:
            product.synonyms = data.synonyms
        if data.min_stock is not None:
            product.min_stock = data.min_stock
        if data.min_stock_unit is not None:
            product.min_stock_unit = data.min_stock_unit

        self.db.flush()
        return product

    def delete(self, product_id: int) -> None:
        product = self.get(product_id)
        if not product:
            raise DomainError("Produkt nicht gefunden", {"product_id": product_id})

        has_stock = self.db.execute(
            select(StockEntry).where(StockEntry.product_id == product_id).limit(1)
        ).scalar_one_or_none()
        if has_stock:
            raise DomainError(
                "Produkt hat noch Bestandseintraege und kann nicht geloescht werden",
                {"product_id": product_id},
            )

        self.db.delete(product)
        self.db.flush()
