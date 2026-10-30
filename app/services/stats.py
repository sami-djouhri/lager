"""Stats service: consumption analytics, expiry forecast, waste summary."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.domain import fifo_sort_key
from app.models import ConsumptionEvent, Product, StockEntry

# Gruende, die eine Buchung zu einem Verlust machen. Alles andere ist ein
# regulaerer Abgang: ein neuer Grund wie "verschenkt" zaehlt damit nicht als
# Verschwendung, und das ist die sichere Seite.
VERLUST_GRUENDE = ("weggeworfen", "abgelaufen")


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
                ConsumptionEvent.reason.in_(VERLUST_GRUENDE),
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
        """Verlustquote je Kategorie, gerechnet aus GEBUCHTEN Entsorgungen.

        Bis zum 2026-10-24 stand hier
        ``abgelaufene Lots / (Verbrauchsmenge + abgelaufene Lots)``, und das
        hatte drei Fehler in einer Zeile:

        1. Der Zaehler war eine **Anzahl** (Lots), der Nenner mischte Anzahl
           und **Menge**. Ein Verhaeltnis aus zwei Dimensionen ist keine Quote.
        2. Die Verbrauchsmenge addierte Gramm, Milliliter und Stueck zu einer
           Zahl -- genau das, was ``_totals_by_product_unit`` zwei Methoden
           weiter unten ausdruecklich vermeidet.
        3. Das Fenster ``days`` galt nur fuer den Verbrauch, nicht fuer die
           Abgelaufenen. Ein vor acht Monaten abgelaufener Posten zaehlte
           damit dauerhaft in jede 30-Tage-Quote, und er wurde mit jedem Tag
           schwerer, weil der Verbrauch im Nenner wegfiel.

        Gemessen am 2026-10-24 ergab das **100,0 % Verlust in sechs von sieben
        Kategorien**, waehrend der Nachbar-Tab derselben Seite
        (``/api/stats/waste``, der nur echte Entsorgungsbuchungen zaehlt)
        ``total_events: 0`` lieferte und "Keine Verschwendung - weiter so!"
        anzeigte. Zwei Antworten auf dieselbe Frage, maximal auseinander, auf
        einer Seite, und beide sahen wie eine Messung aus.

        Jetzt tragen Zaehler und Nenner dasselbe Fenster und dieselbe Einheit:
        je (Kategorie, Einheit) stehen Verlustmenge und Gesamtabgang
        nebeneinander. ``waste_percent`` der Kategorie ist die Quote der
        Einheit mit der groessten Bewegung, und ``waste_unit`` nennt sie --
        eine Prozentzahl ohne benannte Dimension waere wieder dasselbe
        Problem. Die Wahl der Leiteinheit folgt ``turnover_rates``: groesste
        Menge gewinnt, bei Gleichstand der Name, damit die Antwort
        reproduzierbar ist.

        ``expired_in_stock`` bleibt erhalten, zaehlt aber **nicht** in die
        Quote. Es ist ein Bestandsmaß, kein Verlustmaß: ein MHD ist kein
        Verfallsdatum, und was noch im Regal liegt, ist nicht weggeworfen.
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)
        today = date.today()
        OHNE = "Ohne Kategorie"

        # --- Aktive Lots je Kategorie ---
        active_stmt = (
            select(
                Product.category,
                func.count(StockEntry.id).label("anzahl"),
            )
            .join(Product, StockEntry.product_id == Product.id)
            .where(StockEntry.quantity > 0)
            .group_by(Product.category)
        )
        aktive = {
            r.category or OHNE: r.anzahl for r in self.db.execute(active_stmt).all()
        }

        # --- Abgelaufen und noch im Regal (ohne Zeitfenster, das ist Bestand) ---
        expired_stmt = (
            select(
                Product.category,
                func.count(StockEntry.id).label("anzahl"),
            )
            .join(Product, StockEntry.product_id == Product.id)
            .where(StockEntry.mhd < today, StockEntry.quantity > 0)
            .group_by(Product.category)
        )
        abgelaufen = {
            r.category or OHNE: r.anzahl for r in self.db.execute(expired_stmt).all()
        }

        # --- Buchungen im Fenster, je (Kategorie, Einheit) und Verlust-Kennzeichen ---
        # EIN Durchlauf mit dem Verlust-Kennzeichen als Gruppierungsspalte,
        # nicht zwei Abfragen mit `in_` und `notin_`. Grund ist NULL: ein
        # `reason IS NULL` erfuellt weder `in_` noch `notin_` und faellt aus
        # BEIDEN Zweigen, verschwindet also lautlos aus Zaehler UND Nenner
        # Als Gruppierungsspalte kommt
        # er als eigene Gruppe mit `verlust = None` zurueck und landet unten im
        # falsy-Zweig, also beim regulaeren Abgang -- der Seite, die niemanden
        # alarmiert. Die Spalte ist NOT NULL, aber darauf soll die Rechnung
        # nicht angewiesen sein.
        ist_verlust = ConsumptionEvent.reason.in_(VERLUST_GRUENDE)
        buchung_stmt = (
            select(
                Product.category,
                ConsumptionEvent.unit,
                ist_verlust.label("verlust"),
                func.sum(ConsumptionEvent.amount).label("menge"),
                func.count(ConsumptionEvent.id).label("anzahl"),
            )
            .join(StockEntry, ConsumptionEvent.stock_entry_id == StockEntry.id)
            .join(Product, StockEntry.product_id == Product.id)
            .where(ConsumptionEvent.consumed_at >= since)
            .group_by(Product.category, ConsumptionEvent.unit, ist_verlust)
        )

        # (kategorie, einheit) -> {"consumed": .., "discarded": ..}
        mengen: dict[tuple[str, str], dict[str, float]] = {}
        buchungen: dict[str, int] = {}
        verluste: dict[str, int] = {}
        for r in self.db.execute(buchung_stmt).all():
            cat = r.category or OHNE
            eintrag = mengen.setdefault(
                (cat, r.unit), {"consumed": 0.0, "discarded": 0.0}
            )
            feld = "discarded" if r.verlust else "consumed"
            eintrag[feld] += float(r.menge or 0.0)
            buchungen[cat] = buchungen.get(cat, 0) + r.anzahl
            if r.verlust:
                verluste[cat] = verluste.get(cat, 0) + r.anzahl

        # --- Zusammenfuehren ---
        je_kategorie: dict[str, list[dict]] = {}
        for (cat, unit), werte in mengen.items():
            gesamt = werte["consumed"] + werte["discarded"]
            je_kategorie.setdefault(cat, []).append({
                "unit": unit,
                "consumed": round(werte["consumed"], 2),
                "discarded": round(werte["discarded"], 2),
                "waste_percent": (
                    round(werte["discarded"] / gesamt * 100, 1) if gesamt > 0 else 0.0
                ),
            })

        result = []
        for cat in set(aktive) | set(abgelaufen) | set(je_kategorie):
            by_unit = sorted(je_kategorie.get(cat, []), key=lambda e: e["unit"])
            # Leiteinheit: groesste Bewegung, bei Gleichstand der Einheitenname.
            leit = max(
                by_unit,
                key=lambda e: (e["consumed"] + e["discarded"], e["unit"]),
                default=None,
            )
            result.append({
                "category": cat,
                "active_items": aktive.get(cat, 0),
                "expired_in_stock": abgelaufen.get(cat, 0),
                "waste_percent": leit["waste_percent"] if leit else 0.0,
                "waste_unit": leit["unit"] if leit else None,
                "events_total": buchungen.get(cat, 0),
                "events_discarded": verluste.get(cat, 0),
                "by_unit": by_unit,
            })

        # Schlechteste Kategorien zuerst; bei gleicher Quote die mit mehr
        # Verlustbuchungen, dann nach Name, damit die Reihenfolge stabil ist.
        result.sort(
            key=lambda r: (-r["waste_percent"], -r["events_discarded"], r["category"])
        )
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

        Der Anlass: mealprep rief ``/api/stats/turnover/{id}`` einmal je
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
