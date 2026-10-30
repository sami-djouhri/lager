"""Stats service tests: including N+1 query-count regression guards.

The `expiry_forecast()` and `critical_stock()` paths read StockEntry rows and
then dereference `entry.product.name`. If `joinedload(StockEntry.product)` is
ever dropped, those become 1 follow-up SELECT per row (N+1). These tests pin
the query count so the joinedload can't silently regress.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import event

from app.models import Product, StockEntry
from app.services.stats import StatsService
from tests.conftest import TEST_ENGINE


@pytest.fixture
def sample_stock(db_session):
    """Create 10 products + 10 stock entries with varied MHDs."""
    today = date.today()
    products = [
        Product(
            name=f"Produkt {i}",
            default_unit="Stück",
            min_stock=5.0,
        )
        for i in range(10)
    ]
    db_session.add_all(products)
    db_session.flush()

    entries = []
    for i, product in enumerate(products):
        entries.append(
            StockEntry(
                product_id=product.id,
                quantity=10.0,
                unit="Stück",
                mhd=today + timedelta(days=i - 3),
                purchase_date=today,
                location="Lager",
            )
        )
    db_session.add_all(entries)
    db_session.commit()
    return products, entries


class _QueryCounter:
    """Count SELECT statements on TEST_ENGINE for the duration of a `with` block."""

    def __init__(self):
        self.count = 0
        self.statements: list[str] = []

    def _before(self, conn, cursor, statement, *_args, **_kw):
        if statement.lstrip().upper().startswith("SELECT"):
            self.count += 1
            self.statements.append(statement)

    def __enter__(self):
        event.listen(TEST_ENGINE, "before_cursor_execute", self._before)
        return self

    def __exit__(self, *_exc):
        event.remove(TEST_ENGINE, "before_cursor_execute", self._before)


def test_expiry_forecast_no_n_plus_one(db_session, sample_stock):
    products, _entries = sample_stock
    stats = StatsService(db_session)

    db_session.expire_all()  # force fresh load
    with _QueryCounter() as qc:
        result = stats.expiry_forecast()

    assert len(result) == len(products)
    # With joinedload Product is eagerly fetched in the same SELECT.
    # Allow up to 2 queries (1 for entries+products joinedload, 1 buffer for
    # SQLAlchemy unique() bookkeeping). >=3 is an N+1 regression.
    assert qc.count <= 2, (
        f"expiry_forecast() executed {qc.count} SELECTs: joinedload regression. "
        f"Statements: {qc.statements}"
    )


def test_critical_stock_no_n_plus_one(db_session, sample_stock):
    stats = StatsService(db_session)

    db_session.expire_all()
    with _QueryCounter() as qc:
        result = stats.critical_stock()

    # Result depth depends on min_stock + mhd thresholds; just assert it ran.
    assert isinstance(result, list)
    # critical_stock executes 3 deliberate SELECTs (totals, products-w-min_stock,
    # expiring-lots). The N+1 would push that into double digits per row.
    assert qc.count <= 5, (
        f"critical_stock() executed {qc.count} SELECTs: joinedload regression. "
        f"Statements: {qc.statements}"
    )


def test_expiry_forecast_returns_product_names(db_session, sample_stock):
    products, _entries = sample_stock
    stats = StatsService(db_session)

    result = stats.expiry_forecast()
    names = {row["product_name"] for row in result}
    expected = {p.name for p in products}
    assert names == expected


def test_low_stock_multi_unit_does_not_collapse(client):
    """Bestand in mehreren Einheiten pro Produkt darf sich nicht überschreiben.

    Bug: totals-Dict war nach product_id gekeyt, Query gruppierte aber nach
    (product_id, unit): die letzte Einheit gewann und min_stock-Vergleiche
    nutzten eine zufällige Teilmenge.
    """
    pid = client.post("/api/products", json={
        "name": "Nudeln-MultiUnit", "default_unit": "g",
        "min_stock": 500, "min_stock_unit": "g",
    }).json()["id"]
    # 100 g (unter min_stock) + 10 piece (andere Einheit, darf nicht zählen)
    client.post("/api/stock", json={"product_id": pid, "quantity": 100, "unit": "g"})
    client.post("/api/stock", json={"product_id": pid, "quantity": 10, "unit": "piece"})

    low = client.get("/api/stats/low-stock").json()
    row = next((r for r in low if r["product_id"] == pid), None)
    assert row is not None, "Produkt fehlt in low-stock trotz 100g < 500g min_stock"
    assert row["current_stock"] == 100
    assert row["min_stock_unit"] == "g"

    critical = client.get("/api/critical").json()["critical"]
    crow = next((r for r in critical if r["product_id"] == pid), None)
    assert crow is not None
    assert crow["current_qty"] == 100
