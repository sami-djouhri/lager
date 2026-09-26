"""Einkaufslisten-Service: leitet Vorschläge aus low_stock + Verbrauch + Ablauf ab."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ConsumptionEvent, Product, StockEntry

REASON_LOW_STOCK = "low_stock"
REASON_WEEKLY_AVERAGE = "weekly_average"
REASON_EXPIRING_SOON = "expiring_soon"

VALID_REASONS = {REASON_LOW_STOCK, REASON_WEEKLY_AVERAGE, REASON_EXPIRING_SOON}


@dataclass
class ShoppingSuggestion:
    product_id: int
    product_name: str
    suggested_quantity: float
    unit: str
    reason: str
    current_stock: float

    def as_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "suggested_quantity": round(self.suggested_quantity, 2),
            "unit": self.unit,
            "reason": self.reason,
            "current_stock": round(self.current_stock, 2),
        }


class ShoppingService:
    """Kombiniert Bestands- und Verbrauchssicht zu konkreten Einkaufsvorschlägen."""

    def __init__(self, db: Session):
        self.db = db

    def suggestions(
        self,
        *,
        analysis_days: int = 30,
        expiring_within_days: int = 7,
    ) -> list[dict]:
        totals = self._totals_by_product()
        suggestions: dict[int, ShoppingSuggestion] = {}

        # 1) Low-stock-getriebene Vorschläge (höchste Priorität → dürfen nicht überschrieben werden)
        for product in self._products_with_min_stock():
            unit = product.min_stock_unit or product.default_unit
            current = totals.get((product.id, unit), 0.0)
            if current < product.min_stock:
                deficit = product.min_stock - current
                suggestions[product.id] = ShoppingSuggestion(
                    product_id=product.id,
                    product_name=product.name,
                    suggested_quantity=deficit,
                    unit=unit,
                    reason=REASON_LOW_STOCK,
                    current_stock=current,
                )

        # 2) Weekly-average: Produkte, deren erwarteter Wochenbedarf höher ist als der Bestand
        for row in self._weekly_consumption(analysis_days):
            if row["product_id"] in suggestions:
                continue
            current = totals.get((row["product_id"], row["unit"]), 0.0)
            weekly = row["weekly_avg"]
            if weekly > 0 and current < weekly:
                suggestions[row["product_id"]] = ShoppingSuggestion(
                    product_id=row["product_id"],
                    product_name=row["product_name"],
                    suggested_quantity=weekly,
                    unit=row["unit"],
                    reason=REASON_WEEKLY_AVERAGE,
                    current_stock=current,
                )

        # 3) Expiring-soon: Replacement-Hinweis nur, wenn Produkt nicht ohnehin schon drauf ist
        for row in self._expiring_products(expiring_within_days):
            if row["product_id"] in suggestions:
                continue
            current = totals.get((row["product_id"], row["unit"]), 0.0)
            suggestions[row["product_id"]] = ShoppingSuggestion(
                product_id=row["product_id"],
                product_name=row["product_name"],
                suggested_quantity=row["expiring_quantity"],
                unit=row["unit"],
                reason=REASON_EXPIRING_SOON,
                current_stock=current,
            )

        # Sort: low_stock zuerst, dann weekly_average, dann expiring_soon, innerhalb nach Name.
        priority = {REASON_LOW_STOCK: 0, REASON_WEEKLY_AVERAGE: 1, REASON_EXPIRING_SOON: 2}
        ordered = sorted(
            suggestions.values(),
            key=lambda s: (priority[s.reason], s.product_name.lower()),
        )
        return [s.as_dict() for s in ordered]

    # ------------------------------------------------------------------ helpers

    def _totals_by_product(self) -> dict[tuple[int, str], float]:
        stmt = (
            select(
                StockEntry.product_id,
                StockEntry.unit,
                func.sum(StockEntry.quantity).label("total"),
            )
            .where(StockEntry.quantity > 0)
            .group_by(StockEntry.product_id, StockEntry.unit)
        )
        return {(r.product_id, r.unit): float(r.total) for r in self.db.execute(stmt).all()}

    def _products_with_min_stock(self):
        stmt = select(Product).where(
            Product.min_stock.is_not(None), Product.min_stock > 0
        )
        return list(self.db.execute(stmt).scalars().all())

    def _weekly_consumption(self, days: int) -> list[dict]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = (
            select(
                StockEntry.product_id,
                Product.name,
                ConsumptionEvent.unit,
                func.sum(ConsumptionEvent.amount).label("total_amount"),
            )
            .join(StockEntry, ConsumptionEvent.stock_entry_id == StockEntry.id)
            .join(Product, StockEntry.product_id == Product.id)
            .where(ConsumptionEvent.consumed_at >= since)
            .group_by(StockEntry.product_id, Product.name, ConsumptionEvent.unit)
        )
        rows = self.db.execute(stmt).all()
        return [
            {
                "product_id": r.product_id,
                "product_name": r.name,
                "unit": r.unit,
                "weekly_avg": float(r.total_amount) / (days / 7.0),
            }
            for r in rows
        ]

    def _expiring_products(self, within_days: int) -> list[dict]:
        cutoff = date.today() + timedelta(days=within_days)
        stmt = (
            select(
                StockEntry.product_id,
                Product.name,
                StockEntry.unit,
                func.sum(StockEntry.quantity).label("expiring_qty"),
            )
            .join(Product, StockEntry.product_id == Product.id)
            .where(
                StockEntry.quantity > 0,
                StockEntry.mhd.is_not(None),
                StockEntry.mhd <= cutoff,
            )
            .group_by(StockEntry.product_id, Product.name, StockEntry.unit)
        )
        rows = self.db.execute(stmt).all()
        return [
            {
                "product_id": r.product_id,
                "product_name": r.name,
                "unit": r.unit,
                "expiring_quantity": float(r.expiring_qty),
            }
            for r in rows
        ]


def forecast(
    db: Session,
    *,
    days: int = 14,
    kind: str = "expire",
) -> list[dict]:
    """Generalisierter Forecast: `expire` für MHD-basiert, `run_out` für Bestands-/Verbrauchs-basiert.

    Beide Modi liefern dieselbe Schema-Struktur {product_id, product_name, days_left, reason}.
    """
    if kind not in {"expire", "run_out"}:
        raise ValueError(f"unknown forecast kind: {kind}")

    today = date.today()
    cutoff = today + timedelta(days=days)
    results: list[dict] = []

    if kind == "expire":
        stmt = (
            select(StockEntry, Product)
            .join(Product, StockEntry.product_id == Product.id)
            .where(
                StockEntry.quantity > 0,
                StockEntry.mhd.is_not(None),
                StockEntry.mhd <= cutoff,
            )
        )
        for entry, product in db.execute(stmt).all():
            results.append({
                "product_id": product.id,
                "product_name": product.name,
                "days_left": (entry.mhd - today).days,
                "quantity": entry.quantity,
                "unit": entry.unit,
                "reason": "expire",
            })
    else:  # run_out
        svc = ShoppingService(db)
        totals = svc._totals_by_product()
        weekly_rows = svc._weekly_consumption(days=max(days, 14))
        for row in weekly_rows:
            current = totals.get((row["product_id"], row["unit"]), 0.0)
            daily = row["weekly_avg"] / 7.0
            if daily <= 0:
                continue
            days_left = int(current / daily) if current > 0 else 0
            if days_left > days:
                continue
            results.append({
                "product_id": row["product_id"],
                "product_name": row["product_name"],
                "days_left": days_left,
                "quantity": current,
                "unit": row["unit"],
                "reason": "run_out",
            })

    results.sort(key=lambda r: (r["days_left"], r["product_name"].lower()))
    return results
