"""Stock service: booking in/out, FIFO consumption, availability, expiry."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain import DomainError, assert_unit_compatible, fifo_sort_key
from app.models import ConsumptionEvent, Product, StockEntry
from app.schemas import StockEntryCreate, StockEntryUpdate


def check_low_stock(db: Session, product_id: int) -> dict | None:
    """Prüft, ob Produkt unter min_stock liegt. None wenn ok oder kein min_stock gesetzt."""
    product = db.get(Product, product_id)
    if not product or not product.min_stock or product.min_stock <= 0:
        return None
    unit = product.min_stock_unit or product.default_unit
    total = db.execute(
        select(func.coalesce(func.sum(StockEntry.quantity), 0.0)).where(
            StockEntry.product_id == product_id,
            StockEntry.unit == unit,
            StockEntry.quantity > 0,
        )
    ).scalar()
    current = round(float(total), 4)
    if current >= product.min_stock:
        return None
    return {
        "product_id": product_id,
        "product_name": product.name,
        "current_stock": current,
        "min_stock": product.min_stock,
        "min_stock_unit": unit,
        "deficit": round(product.min_stock - current, 4),
    }


class StockService:
    def __init__(self, db: Session):
        self.db = db

    # ----- queries -----

    def list_entries(
        self,
        product_id: int | None = None,
        location: str | None = None,
        only_positive: bool = True,
        offset: int = 0,
        limit: int = 200,
    ) -> tuple[list[StockEntry], int]:
        stmt = select(StockEntry)
        if product_id is not None:
            stmt = stmt.where(StockEntry.product_id == product_id)
        if location:
            stmt = stmt.where(StockEntry.location == location)
        if only_positive:
            stmt = stmt.where(StockEntry.quantity > 0)
        rows = sorted(self.db.execute(stmt).scalars().all(), key=fifo_sort_key)
        return rows[offset : offset + limit], len(rows)

    def get_entry(self, entry_id: int) -> StockEntry | None:
        return self.db.get(StockEntry, entry_id)

    def get_available(self, product_id: int, unit: str) -> float:
        stmt = select(StockEntry).where(
            StockEntry.product_id == product_id,
            StockEntry.unit == unit,
            StockEntry.quantity > 0,
        )
        rows = self.db.execute(stmt).scalars().all()
        return round(sum(r.quantity for r in rows), 4)

    def get_expiring(self, days: int = 7) -> list[StockEntry]:
        cutoff = date.today() + timedelta(days=days)
        stmt = select(StockEntry).where(
            StockEntry.quantity > 0,
            StockEntry.mhd is not None,
            StockEntry.mhd <= cutoff,
        )
        rows = self.db.execute(stmt).scalars().all()
        return sorted(rows, key=fifo_sort_key)

    # ----- mutations -----

    def add(self, data: StockEntryCreate) -> StockEntry:
        product = self.db.get(Product, data.product_id)
        if not product:
            raise DomainError(
                "Produkt nicht gefunden", {"product_id": data.product_id}
            )
        entry = StockEntry(
            product_id=data.product_id,
            quantity=data.quantity,
            unit=data.unit,
            mhd=data.mhd,
            purchase_date=data.purchase_date,
            location=data.location,
            lot_note=data.lot_note,
        )
        self.db.add(entry)
        self.db.flush()
        return entry

    def update_entry(self, entry_id: int, data: StockEntryUpdate) -> StockEntry:
        entry = self.get_entry(entry_id)
        if not entry:
            raise DomainError(
                "Bestandseintrag nicht gefunden", {"entry_id": entry_id}
            )
        if data.quantity is not None:
            entry.quantity = data.quantity
        if data.unit is not None:
            entry.unit = data.unit
        if data.mhd is not None:
            entry.mhd = data.mhd
        if data.purchase_date is not None:
            entry.purchase_date = data.purchase_date
        if data.location is not None:
            entry.location = data.location
        if data.lot_note is not None:
            entry.lot_note = data.lot_note
        if data.opened_at is not None:
            entry.opened_at = data.opened_at
        self.db.flush()
        return entry

    def delete_entry(self, entry_id: int) -> None:
        entry = self.get_entry(entry_id)
        if not entry:
            raise DomainError(
                "Bestandseintrag nicht gefunden", {"entry_id": entry_id}
            )
        self.db.delete(entry)
        self.db.flush()

    # ----- FIFO consumption -----

    def consume(
        self,
        product_id: int,
        amount: float,
        unit: str,
        reason: str = "verbraucht",
        source: str = "manual",
        ref_type: str | None = None,
        ref_id: int | None = None,
    ) -> list[ConsumptionEvent]:
        entries = self._sorted_entries(product_id, unit)
        if not entries:
            raise DomainError(
                f"Kein Bestand fuer Produkt {product_id}",
                {"product_id": product_id},
            )

        events: list[ConsumptionEvent] = []
        remaining = round(amount, 4)
        for entry in entries:
            if remaining <= 0:
                break
            assert_unit_compatible(unit, entry.unit)
            take = round(min(entry.quantity, remaining), 4)
            entry.quantity = round(entry.quantity - take, 4)
            remaining = round(remaining - take, 4)
            event = ConsumptionEvent(
                stock_entry_id=entry.id,
                amount=take,
                unit=unit,
                reason=reason,
                source=source,
                ref_type=ref_type,
                ref_id=ref_id,
            )
            self.db.add(event)
            events.append(event)

        if remaining > 0.001:
            raise DomainError(
                f"Nicht genug Bestand: {amount} {unit} angefordert, "
                f"{round(amount - remaining, 4):.1f} verfuegbar",
                {"product_id": product_id, "missing": round(remaining, 4)},
            )

        self.db.flush()
        return events

    def consume_for_recipe(
        self,
        recipe_ingredients: list[dict],
        source: str = "mealprep",
        ref_type: str | None = "recipe",
        ref_id: int | None = None,
    ) -> list[ConsumptionEvent]:
        # Pre-check: all ingredients available
        missing = []
        for ing in recipe_ingredients:
            avail = self.get_available(ing["product_id"], ing["unit"])
            if avail < ing["amount"] - 0.001:
                missing.append({
                    "product_id": ing["product_id"],
                    "needed": round(ing["amount"], 2),
                    "available": round(avail, 2),
                    "unit": ing["unit"],
                })
        if missing:
            raise DomainError("Zutaten fehlen", {"missing": missing})

        # Consume all ingredients
        all_events: list[ConsumptionEvent] = []
        for ing in recipe_ingredients:
            events = self.consume(
                product_id=ing["product_id"],
                amount=ing["amount"],
                unit=ing["unit"],
                reason=ing.get("reason", "verbraucht"),
                source=source,
                ref_type=ref_type,
                ref_id=ref_id,
            )
            all_events.extend(events)

        return all_events

    # ----- internal -----

    def _sorted_entries(self, product_id: int, unit: str) -> list[StockEntry]:
        stmt = select(StockEntry).where(
            StockEntry.product_id == product_id,
            StockEntry.unit == unit,
            StockEntry.quantity > 0,
        )
        rows = self.db.execute(stmt).scalars().all()
        return sorted(rows, key=fifo_sort_key)
