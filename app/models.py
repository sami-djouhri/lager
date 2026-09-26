"""ORM models: Product, StockEntry, ConsumptionEvent, ElectronicAsset."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.db import Base

# Multi-Tenant: gehoert eine Zeile zu keinem sub (Alt-Daten/Backfill), dann Owner.
_OWNER = settings.DEFAULT_OWNER_SUB


# ---------------------------------------------------------------------------
# JSON helpers (same pattern as MealPrep)
# ---------------------------------------------------------------------------

def _json_default(val: Any) -> str | None:
    if val is None:
        return None
    return json.dumps(val, ensure_ascii=False)


def _json_load(raw: str | None) -> Any:
    if raw is None:
        return None
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Product – Stammdaten
# ---------------------------------------------------------------------------

class Product(Base):
    __tablename__ = "product"
    # Eindeutigkeit pro Tenant statt global (sonst blockiert Tenant A den Namen/Barcode fuer B).
    __table_args__ = (
        UniqueConstraint("owner_sub", "name", name="uq_product_owner_name"),
        UniqueConstraint("owner_sub", "barcode", name="uq_product_owner_barcode"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_sub: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True, server_default=_OWNER
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    default_unit: Mapped[str] = mapped_column(String(20), default="g")
    nutrition_per_100_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    typical_pack_sizes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    shelf_life_type: Mapped[str] = mapped_column(String(10), default="MHD")
    shelf_life_days_default: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    synonyms_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    min_stock: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_stock_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    stock_entries: Mapped[list[StockEntry]] = relationship(
        "StockEntry", back_populates="product", cascade="all, delete-orphan"
    )

    # --- JSON properties ---

    @property
    def nutrition_per_100(self) -> dict | None:
        return _json_load(self.nutrition_per_100_json)

    @nutrition_per_100.setter
    def nutrition_per_100(self, val: dict | None) -> None:
        self.nutrition_per_100_json = _json_default(val)

    @property
    def typical_pack_sizes(self) -> list[int]:
        return _json_load(self.typical_pack_sizes_json) or []

    @typical_pack_sizes.setter
    def typical_pack_sizes(self, val: list[int]) -> None:
        self.typical_pack_sizes_json = _json_default(val)

    @property
    def synonyms(self) -> list[str]:
        return _json_load(self.synonyms_json) or []

    @synonyms.setter
    def synonyms(self, val: list[str]) -> None:
        self.synonyms_json = _json_default(val)


# ---------------------------------------------------------------------------
# StockEntry – Lagerbestand
# ---------------------------------------------------------------------------

class StockEntry(Base):
    __tablename__ = "stock_entry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_sub: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True, server_default=_OWNER
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("product.id"), nullable=False
    )
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="g")
    mhd: Mapped[date | None] = mapped_column(Date, nullable=True)
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    location: Mapped[str] = mapped_column(String(50), default="Vorratskammer")
    lot_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )
    opened_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    product: Mapped[Product] = relationship("Product", back_populates="stock_entries")
    consumption_events: Mapped[list[ConsumptionEvent]] = relationship(
        "ConsumptionEvent", back_populates="stock_entry"
    )


# ---------------------------------------------------------------------------
# ConsumptionEvent – Verbrauchsbuchung
# ---------------------------------------------------------------------------

class ConsumptionEvent(Base):
    __tablename__ = "consumption_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_sub: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True, server_default=_OWNER
    )
    stock_entry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stock_entry.id"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    consumed_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )
    reason: Mapped[str] = mapped_column(String(20), default="verbraucht")
    source: Mapped[str] = mapped_column(String(20), default="manual")
    ref_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    stock_entry: Mapped[StockEntry] = relationship(
        "StockEntry", back_populates="consumption_events"
    )


# ---------------------------------------------------------------------------
# ElectronicAsset – Einzelstuecke: Elektronik, eBay-/Reselling-Zeug
# ---------------------------------------------------------------------------

class ElectronicAsset(Base):
    __tablename__ = "electronic_asset"
    __table_args__ = (
        UniqueConstraint("owner_sub", "serial", name="uq_electronic_asset_owner_serial"),
        UniqueConstraint("owner_sub", "barcode", name="uq_electronic_asset_owner_barcode"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_sub: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True, server_default=_OWNER
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(150), nullable=True)
    serial: Mapped[str | None] = mapped_column(String(150), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(50), nullable=True)

    condition: Mapped[str] = mapped_column(String(30), default="gut", index=True)
    status: Mapped[str] = mapped_column(String(30), default="aktiv", index=True)
    location: Mapped[str] = mapped_column(String(80), default="Elektronik")
    usage_status: Mapped[str] = mapped_column(String(30), default="reserve", index=True)
    homelab_role: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    host_name: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    service_refs_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    purchase_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    purchase_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    purchase_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    warranty_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    estimated_resale_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    resale_confidence: Mapped[str | None] = mapped_column(String(30), nullable=True)
    sell_decision: Mapped[str] = mapped_column(String(30), default="behalten", index=True)
    sell_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    desired_min_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    manual_pin: Mapped[int] = mapped_column(Integer, default=0, index=True)

    # Live-Marktwert (marktwatch-Median), getrennt vom manuellen estimated_resale_value.
    market_value_eur: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_value_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    ebay_item_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    ebay_watch_query: Mapped[str | None] = mapped_column(String(250), nullable=True)
    external_refs_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    @property
    def external_refs(self) -> dict:
        return _json_load(self.external_refs_json) or {}

    @external_refs.setter
    def external_refs(self, val: dict | None) -> None:
        self.external_refs_json = _json_default(val or {})

    @property
    def estimated_profit(self) -> float | None:
        if self.estimated_resale_value is None or self.purchase_price is None:
            return None
        return round(self.estimated_resale_value - self.purchase_price, 2)

    @property
    def service_refs(self) -> list[str]:
        return _json_load(self.service_refs_json) or []

    @service_refs.setter
    def service_refs(self, val: list[str] | None) -> None:
        self.service_refs_json = _json_default(val or [])

    @property
    def in_active_use(self) -> bool:
        return self.usage_status in {"homelab_active", "daily_use", "critical"}

    @property
    def effective_market_value(self) -> float | None:
        # Marktwert (live) gewinnt, manueller Schätzwert ist Fallback.
        if self.market_value_eur is not None:
            return self.market_value_eur
        return self.estimated_resale_value
