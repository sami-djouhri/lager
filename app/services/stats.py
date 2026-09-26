"""Stats service: consumption analytics, expiry forecast, waste summary."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.domain import fifo_sort_key
from app.models import ConsumptionEvent, Product, StockEntry


class StatsService:
    def __init__(self, db: Session):
        self.db = db

    def consumption_by_product(self, days: int = 30) -> list[dict]:
        """Top consumed products in the last N days."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = (
            select(
                StockEntry.product_id,
                Product.name,
                ConsumptionEvent.unit,
                func.sum(ConsumptionEvent.amount).label("total_amount"),
                func.count(ConsumptionEvent.id).label("event_count"),
            )
            .join(StockEntry, ConsumptionEvent.stock_entry_id == StockEntry.id)
            .join(Product, StockEntry.product_id == Product.id)
            .where(ConsumptionEvent.consumed_at >= since)
            .group_by(StockEntry.product_id, Product.name, ConsumptionEvent.unit)
            .order_by(func.sum(ConsumptionEvent.amount).desc())
        )
        rows = self.db.execute(stmt).all()
        return [
            {
                "product_id": r.product_id,
                "product_name": r.name,
                "total_amount": round(r.total_amount, 2),
                "unit": r.unit,
                "event_count": r.event_count,
            }
            for r in rows
        ]

    def waste_summary(self, days: int = 30) -> dict:
        """Summary of wasted items (reason=weggeworfen or abgelaufen)."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = (
            select(
                StockEntry.product_id,
                Product.name,
                ConsumptionEvent.unit,
                func.sum(ConsumptionEvent.amount).label("total_amount"),
                func.count(ConsumptionEvent.id).label("event_count"),
            )
            .join(StockEntry, ConsumptionEvent.stock_entry_id == StockEntry.id)
            .join(Product, StockEntry.product_id == Product.id)
            .where(
                ConsumptionEvent.consumed_at >= since,
                ConsumptionEvent.reason.in_(["weggeworfen", "abgelaufen"]),
            )
            .group_by(StockEntry.product_id, Product.name, ConsumptionEvent.unit)
            .order_by(func.sum(ConsumptionEvent.amount).desc())
        )
        rows = self.db.execute(stmt).all()
        by_product = [
            {
                "product_id": r.product_id,
                "product_name": r.name,
                "total_amount": round(r.total_amount, 2),
                "unit": r.unit,
                "event_count": r.event_count,
            }
            for r in rows
        ]
        return {
            "total_events": sum(r["event_count"] for r in by_product),
            "total_amount": sum(r["total_amount"] for r in by_product),
            "by_product": by_product,
        }

    def expiry_forecast(self) -> list[dict]:
        """All stock entries sorted by MHD urgency."""
        stmt = (
            select(StockEntry)
            .options(joinedload(StockEntry.product))
            .where(StockEntry.quantity > 0)
        )
        rows = self.db.execute(stmt).scalars().unique().all()
        today = date.today()
        result = []
        for entry in sorted(rows, key=fifo_sort_key):
            if entry.mhd:
                days_left = (entry.mhd - today).days
                if days_left < 0:
                    urgency = "abgelaufen"
                elif days_left <= 2:
                    urgency = "kritisch"
                elif days_left <= 7:
                    urgency = "bald"
                else:
                    urgency = "ok"
            else:
                days_left = None
                urgency = "ok"

            result.append({
                "product_name": entry.product.name if entry.product else "",
                "quantity": entry.quantity,
                "unit": entry.unit,
                "mhd": entry.mhd,
                "days_left": days_left,
                "urgency": urgency,
                "location": entry.location,
            })
        return result

    def get_category_analytics(self, days: int = 30) -> list[dict]:
        """Per-category breakdown: active items, consumed, expired, waste %."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        today = date.today()

        # --- Active stock entries per category ---
        active_stmt = (
            select(
                Product.category,
                func.count(StockEntry.id).label("total_items"),
            )
            .join(Product, StockEntry.product_id == Product.id)
            .where(StockEntry.quantity > 0)
            .group_by(Product.category)
        )
        active_rows = {
            r.category or "Ohne Kategorie": r.total_items
            for r in self.db.execute(active_stmt).all()
        }

        # --- Total consumed per category in period ---
        consumed_stmt = (
            select(
                Product.category,
                func.sum(ConsumptionEvent.amount).label("total_consumed"),
            )
            .join(StockEntry, ConsumptionEvent.stock_entry_id == StockEntry.id)
            .join(Product, StockEntry.product_id == Product.id)
            .where(ConsumptionEvent.consumed_at >= since)
            .group_by(Product.category)
        )
        consumed_rows = {
            r.category or "Ohne Kategorie": round(r.total_consumed, 2)
            for r in self.db.execute(consumed_stmt).all()
        }

        # --- Expired items per category (mhd < today and quantity > 0) ---
        expired_stmt = (
            select(
                Product.category,
                func.count(StockEntry.id).label("total_expired"),
            )
            .join(Product, StockEntry.product_id == Product.id)
            .where(
                StockEntry.mhd < today,
                StockEntry.quantity > 0,
            )
            .group_by(Product.category)
        )
        expired_rows = {
            r.category or "Ohne Kategorie": r.total_expired
            for r in self.db.execute(expired_stmt).all()
        }

        # --- Merge all categories ---
        all_categories = set(active_rows) | set(consumed_rows) | set(expired_rows)
        result = []
        for cat in all_categories:
            total_consumed = consumed_rows.get(cat, 0.0)
            total_expired = expired_rows.get(cat, 0)
            denominator = total_consumed + total_expired
            waste_pct = round((total_expired / denominator) * 100, 1) if denominator > 0 else 0.0
            result.append({
                "category": cat,
                "total_items": active_rows.get(cat, 0),
                "total_consumed": total_consumed,
                "total_expired": total_expired,
                "waste_percent": waste_pct,
            })

        # Sort by waste_percent descending (worst categories first)
        result.sort(key=lambda r: r["waste_percent"], reverse=True)
        return result

    def critical_stock(self) -> list[dict]:
        """Artikel unter min_stock ODER MHD ≤ heute+2 Tage.

        Aggregiert pro Produkt: ein Item kann mehrere Gründe (`reasons`) und einen
        kombinierten `score` (0..1, höher = dringender) tragen. Sortierung
        absteigend nach score, damit Konsumenten direkt die Top-Risiken sehen.
        """
        today = date.today()
        urgent_mhd = today + timedelta(days=2)
        # Schwelle für Expiry-Score: alles ≤ 0 Tage = score 1.0, ≥ 7 = score 0.
        EXPIRY_HORIZON_DAYS = 7
        items: dict[int, dict] = {}

        totals = self._totals_by_product_unit()

        def _ensure(product_id: int, name: str, unit: str) -> dict:
            it = items.get(product_id)
            if it is None:
                it = {
                    "product_id": product_id,
                    "name": name,
                    "unit": unit,
                    "reasons": [],
                    "score": 0.0,
                }
                items[product_id] = it
            return it

        # 1) Produkte unter min_stock
        products_stmt = select(Product).where(Product.min_stock.is_not(None))
        for product in self.db.execute(products_stmt).scalars().all():
            qty, unit = self._qty_in_reference_unit(product, totals)
            if product.min_stock and product.min_stock > 0 and qty < product.min_stock:
                ratio = max(0.0, min(1.0, qty / product.min_stock))
                stock_score = 1.0 - ratio
                it = _ensure(product.id, product.name, unit)
                it["reasons"].append("unter_min_stock")
                it["current_qty"] = round(qty, 2)
                it["min_stock"] = product.min_stock
                it["score"] = max(it["score"], stock_score)

        # 2) Lots mit bald ablaufendem MHD: pro Produkt schlechtestes Lot wählen.
        expiring_stmt = (
            select(StockEntry)
            .options(joinedload(StockEntry.product))
            .where(StockEntry.quantity > 0, StockEntry.mhd <= urgent_mhd)
        )
        for entry in self.db.execute(expiring_stmt).scalars().unique().all():
            if entry.mhd is None:
                continue
            days_left = (entry.mhd - today).days
            expiry_score = 1.0 if days_left < 0 else max(0.0, 1.0 - days_left / EXPIRY_HORIZON_DAYS)
            name = entry.product.name if entry.product else f"Produkt #{entry.product_id}"
            it = _ensure(entry.product_id, name, entry.unit)
            reason = "abgelaufen" if days_left < 0 else "mhd_kritisch"
            if reason not in it["reasons"]:
                it["reasons"].append(reason)
            prev_days = it.get("days_left")
            if prev_days is None or days_left < prev_days:
                it["days_left"] = days_left
                it["quantity"] = round(entry.quantity, 2)
            # Kombinations-Bonus: beides → score auf 1.0 ziehen.
            base = max(it["score"], expiry_score)
            if "unter_min_stock" in it["reasons"]:
                base = min(1.0, base + 0.2)
            it["score"] = base

        result = sorted(items.values(), key=lambda r: r["score"], reverse=True)
        for it in result:
            it["score"] = round(it["score"], 3)
        return result

    def _totals_by_product_unit(self) -> dict[tuple[int, str], float]:
        """Gesamtmenge pro (Produkt, Einheit): Einheiten dürfen nicht kollabieren."""
        total_stmt = (
            select(
                StockEntry.product_id,
                func.sum(StockEntry.quantity).label("total_qty"),
                StockEntry.unit,
            )
            .where(StockEntry.quantity > 0)
            .group_by(StockEntry.product_id, StockEntry.unit)
        )
        return {
            (r.product_id, r.unit): r.total_qty
            for r in self.db.execute(total_stmt).all()
        }

    @staticmethod
    def _qty_in_reference_unit(
        product: Product, totals: dict[tuple[int, str], float]
    ) -> tuple[float, str]:
        """Bestand in der Vergleichseinheit des Produkts (min_stock_unit/default_unit).

        Bestand in anderen Einheiten desselben Produkts zählt bewusst NICHT gegen
        min_stock, sonst würden z. B. 5 piece einen 500-g-Mindestbestand erfüllen.
        """
        unit = product.min_stock_unit or product.default_unit
        return totals.get((product.id, unit), 0.0), unit

    def low_stock(self, threshold_pct: int = 100) -> list[dict]:
        """Produkte, deren Gesamtmenge unter threshold_pct % des min_stock liegt."""
        totals = self._totals_by_product_unit()

        products_stmt = select(Product).where(Product.min_stock.is_not(None), Product.min_stock > 0)
        result = []
        for product in self.db.execute(products_stmt).scalars().all():
            qty, unit = self._qty_in_reference_unit(product, totals)
            threshold = product.min_stock * threshold_pct / 100
            if qty < threshold:
                deficit = round(threshold - qty, 2)
                shortage_pct = round((1 - qty / product.min_stock) * 100, 1) if product.min_stock > 0 else 100.0
                result.append({
                    "product_id": product.id,
                    "product_name": product.name,
                    "current_stock": round(qty, 2),
                    "min_stock": product.min_stock,
                    "min_stock_unit": unit,
                    "deficit": deficit,
                    "shortage_pct": shortage_pct,
                })
        result.sort(key=lambda r: r["shortage_pct"], reverse=True)
        return result

    def turnover_rates(
        self, product_ids: list[int] | None = None, days: int = 90
    ) -> list[dict]:
        """Verbrauchsrate vieler Produkte in EINEM Durchlauf.

        ★ Der Anlass: mealprep rief ``/api/stats/turnover/{id}`` einmal je
        verknuepfter Zutat. Gemessen am 2026-09-13 kostete ein einziger
        Dashboard-Aufruf 17 Anfragen an lager, 14 davon Turnover. Der Deckel
        liegt bei 60 je Minute, das reichte fuer drei Aufrufe. Mit jeder
        weiteren verknuepften Zutat wird es enger, und was danach kommt, ist
        nicht "langsamer", sondern **falsch**: der Adapter macht aus einem 429
        eine Null, und eine Null sieht aus wie eine Messung.

        ``product_ids=None`` heisst **alle** Produkte mit Verbrauch im
        Zeitraum. Das ist der Fall, den mealprep braucht: ein Aufruf,
        unabhaengig von der Zahl der Zutaten.

        Die Einzelauskunft ``turnover_rate`` rechnet seit dem 2026-09-13 nicht
        mehr selbst, sondern liest hier mit. Zwei Rechenwege fuer dieselbe
        Zahl driften, und der seltener benutzte driftet unbemerkt.
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = (
            select(
                StockEntry.product_id,
                Product.name,
                ConsumptionEvent.unit,
                func.sum(ConsumptionEvent.amount).label("total"),
            )
            .join(StockEntry, ConsumptionEvent.stock_entry_id == StockEntry.id)
            .join(Product, StockEntry.product_id == Product.id)
            .where(ConsumptionEvent.consumed_at >= since)
            .group_by(StockEntry.product_id, Product.name, ConsumptionEvent.unit)
        )
        if product_ids is not None:
            if not product_ids:
                return []
            stmt = stmt.where(StockEntry.product_id.in_(product_ids))
        rows = self.db.execute(stmt).all()

        # Je Produkt die Einheit mit dem hoechsten Gesamtbetrag, dieselbe Wahl
        # wie frueher in der Einzelauskunft. Bei Gleichstand entscheidet der
        # Name der Einheit, damit die Antwort reproduzierbar ist.
        beste: dict[int, tuple] = {}
        for r in rows:
            vorher = beste.get(r.product_id)
            if vorher is None or (r.total, r.unit) > (vorher.total, vorher.unit):
                beste[r.product_id] = r

        return [
            {
                "product_id": r.product_id,
                "product_name": r.name,
                "avg_daily": round(r.total / days, 2),
                "unit": r.unit,
                "days_analysed": days,
            }
            for r in sorted(beste.values(), key=lambda r: r.product_id)
        ]

    def turnover_rate(self, product_id: int, days: int = 90) -> dict | None:
        """Average daily consumption of a product."""
        if not self.db.get(Product, product_id):
            return None
        treffer = self.turnover_rates([product_id], days=days)
        return treffer[0] if treffer else None
