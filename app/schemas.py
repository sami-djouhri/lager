"""Pydantic In/Out schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain import UNIT_SCALE, normalise_unit


def _scale_amount_with_unit(data: dict, amount_key: str, unit_key: str = "unit") -> dict:
    """Skaliert die Menge mit, wenn die Einheit ein Skalierungs-Alias ist (1 kg → 1000 g).

    Muss VOR der Unit-Normalisierung laufen (model_validator mode="before"),
    danach ist die Original-Einheit weg.
    """
    unit = data.get(unit_key)
    amount = data.get(amount_key)
    if isinstance(unit, str) and amount is not None:
        factor = UNIT_SCALE.get(unit.strip().lower())
        if factor is not None and isinstance(amount, (int, float)):
            data[amount_key] = amount * factor
    return data


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    offset: int
    limit: int


# ---------------------------------------------------------------------------
# Nutrition
# ---------------------------------------------------------------------------

class NutritionInfo(BaseModel):
    kcal: float = 0
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0
    fiber_g: float = 0


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

def _normalise_unit_field(v: str | None) -> str | None:
    if v is None:
        return v
    return normalise_unit(v)


class ProductCreate(BaseModel):
    name: str = Field(..., max_length=200)
    barcode: str | None = Field(None, max_length=50)
    category: str | None = Field(None, max_length=100)
    default_unit: str = Field("g", max_length=20)
    nutrition_per_100: NutritionInfo | None = None
    typical_pack_sizes: list[int] = []
    shelf_life_type: str = Field("MHD", max_length=20)
    shelf_life_days_default: int | None = Field(None, ge=0, le=3650)
    image_url: str | None = Field(None, max_length=500)
    synonyms: list[str] = []
    min_stock: float | None = Field(None, ge=0)
    min_stock_unit: str | None = Field(None, max_length=20)

    @model_validator(mode="before")
    @classmethod
    def _scale_min_stock(cls, data):
        if isinstance(data, dict):
            data = _scale_amount_with_unit(data, "min_stock", "min_stock_unit")
        return data

    _norm_default_unit = field_validator("default_unit", "min_stock_unit", mode="before")(
        _normalise_unit_field
    )


class ProductUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    barcode: str | None = Field(None, max_length=50)
    category: str | None = Field(None, max_length=100)
    default_unit: str | None = Field(None, max_length=20)
    nutrition_per_100: NutritionInfo | None = None
    typical_pack_sizes: list[int] | None = None
    shelf_life_type: str | None = Field(None, max_length=20)
    shelf_life_days_default: int | None = None
    image_url: str | None = Field(None, max_length=500)
    synonyms: list[str] | None = None
    min_stock: float | None = None
    min_stock_unit: str | None = Field(None, max_length=20)

    @model_validator(mode="before")
    @classmethod
    def _scale_min_stock(cls, data):
        if isinstance(data, dict) and data.get("min_stock") is not None:
            data = _scale_amount_with_unit(data, "min_stock", "min_stock_unit")
        return data

    _norm_default_unit = field_validator("default_unit", "min_stock_unit", mode="before")(
        _normalise_unit_field
    )


class ProductOut(BaseModel):
    id: int
    name: str
    barcode: str | None
    category: str | None
    default_unit: str
    nutrition_per_100: NutritionInfo | None
    typical_pack_sizes: list[int]
    shelf_life_type: str
    shelf_life_days_default: int | None
    image_url: str | None
    synonyms: list[str] = []
    min_stock: float | None = None
    min_stock_unit: str | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Stock
# ---------------------------------------------------------------------------

class StockEntryCreate(BaseModel):
    product_id: int
    quantity: float = Field(gt=0, le=1_000_000)
    unit: str = Field("g", max_length=20)
    mhd: date | None = None
    purchase_date: date | None = None
    location: str = Field("Vorratskammer", max_length=50)
    lot_note: str | None = Field(None, max_length=200)

    @model_validator(mode="before")
    @classmethod
    def _scale_quantity(cls, data):
        if isinstance(data, dict):
            data = _scale_amount_with_unit(data, "quantity")
        return data

    _norm_unit = field_validator("unit", mode="before")(_normalise_unit_field)


class StockEntryUpdate(BaseModel):
    quantity: float | None = Field(default=None, gt=0, le=1_000_000)
    unit: str | None = Field(None, max_length=20)
    mhd: date | None = None
    purchase_date: date | None = None
    location: str | None = Field(None, max_length=50)
    lot_note: str | None = Field(None, max_length=200)
    opened_at: date | None = None

    @model_validator(mode="before")
    @classmethod
    def _scale_quantity(cls, data):
        # Nur skalieren, wenn quantity UND unit gemeinsam gesetzt werden:
        # eine Unit-Änderung allein darf die Bestandsmenge nicht anfassen.
        if isinstance(data, dict) and data.get("quantity") is not None:
            data = _scale_amount_with_unit(data, "quantity")
        return data

    _norm_unit = field_validator("unit", mode="before")(_normalise_unit_field)


class StockEntryOut(BaseModel):
    id: int
    product_id: int
    product_name: str = ""
    quantity: float
    unit: str
    mhd: date | None
    purchase_date: date | None
    location: str
    days_until_expiry: int | None = None
    opened_at: date | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Consume
# ---------------------------------------------------------------------------

class ConsumeRequest(BaseModel):
    product_id: int
    amount: float = Field(gt=0, le=1_000_000)
    unit: str = Field("g", max_length=20)
    reason: str = Field("verbraucht", max_length=50)
    source: str = Field("manual", max_length=50)
    ref_type: str | None = Field(None, max_length=50)
    ref_id: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _scale_amount(cls, data):
        if isinstance(data, dict):
            data = _scale_amount_with_unit(data, "amount")
        return data

    _norm_unit = field_validator("unit", mode="before")(_normalise_unit_field)


class ConsumeRecipeRequest(BaseModel):
    ingredients: list[ConsumeRequest]


class ConsumptionEventOut(BaseModel):
    id: int
    stock_entry_id: int
    amount: float
    unit: str
    consumed_at: datetime
    reason: str
    source: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class ExpiryForecastItem(BaseModel):
    product_name: str
    quantity: float
    unit: str
    mhd: date | None
    days_left: int | None
    urgency: str
    location: str


class ConsumptionByProduct(BaseModel):
    product_id: int
    product_name: str
    total_amount: float
    unit: str
    event_count: int


class WasteSummary(BaseModel):
    total_events: int
    total_amount: float
    by_product: list[ConsumptionByProduct]


class TurnoverResult(BaseModel):
    product_id: int
    product_name: str
    avg_daily: float
    unit: str
    days_analysed: int


class CategoryAnalyticsItem(BaseModel):
    category: str
    total_items: int
    total_consumed: float
    total_expired: int
    waste_percent: float


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------

class AvailabilityOut(BaseModel):
    product_id: int
    unit: str
    total: float


# ---------------------------------------------------------------------------
# Low Stock
# ---------------------------------------------------------------------------

class LowStockItem(BaseModel):
    product_id: int
    product_name: str
    current_stock: float
    min_stock: float
    min_stock_unit: str
    deficit: float


# ---------------------------------------------------------------------------
# Shopping List / Forecast
# ---------------------------------------------------------------------------

class ShoppingSuggestionOut(BaseModel):
    product_id: int
    product_name: str
    suggested_quantity: float
    unit: str
    reason: str  # low_stock | weekly_average | expiring_soon
    current_stock: float


class ForecastItemOut(BaseModel):
    product_id: int
    product_name: str
    days_left: int
    quantity: float
    unit: str
    reason: str  # expire | run_out


# ---------------------------------------------------------------------------
# Meal Plan
# ---------------------------------------------------------------------------

class MealPlanRequest(BaseModel):
    recipe_ids: list[str]
    servings: int = Field(default=2, ge=1, le=100)


class MealPlanShoppingItem(BaseModel):
    product_id: int
    product_name: str
    needed: float
    available: float
    missing: float
    unit: str


class MealPlanMissingProduct(BaseModel):
    product_id: int | None
    product_name: str
    needed: float
    unit: str


class MealPlanRecipe(BaseModel):
    recipe_id: str
    name: str
    servings: int


class MealPlanResponse(BaseModel):
    requested: list[MealPlanRecipe]
    shopping_list: list[MealPlanShoppingItem]
    missing_stock: list[MealPlanMissingProduct]


class RecipeOut(BaseModel):
    id: str
    name: str
    servings_default: int
    ingredients: list[dict]


# ---------------------------------------------------------------------------
# Electronic Assets
# ---------------------------------------------------------------------------

class ElectronicAssetCreate(BaseModel):
    name: str = Field(..., max_length=200)
    category: str | None = Field(None, max_length=100)
    brand: str | None = Field(None, max_length=100)
    model: str | None = Field(None, max_length=150)
    serial: str | None = Field(None, max_length=150)
    barcode: str | None = Field(None, max_length=50)
    condition: str = Field("gut", max_length=50)
    status: str = Field("aktiv", max_length=50)
    location: str = Field("Elektronik", max_length=80)
    usage_status: str = Field("reserve", max_length=50)
    homelab_role: str | None = Field(None, max_length=100)
    host_name: str | None = Field(None, max_length=100)
    service_refs: list[str] = []
    purchase_date: date | None = None
    purchase_price: float | None = Field(None, ge=0)
    purchase_source: str | None = Field(None, max_length=100)
    purchase_url: str | None = Field(None, max_length=500)
    warranty_end: date | None = None
    estimated_resale_value: float | None = Field(None, ge=0)
    resale_confidence: str | None = Field(None, max_length=50)
    sell_decision: str = Field("behalten", max_length=50)
    sell_reason: str | None = Field(None, max_length=500)
    desired_min_profit: float | None = Field(None, ge=0)
    manual_pin: bool = False
    ebay_item_id: str | None = Field(None, max_length=100)
    ebay_watch_query: str | None = Field(None, max_length=200)
    external_refs: dict = {}
    notes: str | None = Field(None, max_length=2000)


class ElectronicAssetUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    category: str | None = Field(None, max_length=100)
    brand: str | None = Field(None, max_length=100)
    model: str | None = Field(None, max_length=150)
    serial: str | None = Field(None, max_length=150)
    barcode: str | None = Field(None, max_length=50)
    condition: str | None = Field(None, max_length=50)
    status: str | None = Field(None, max_length=50)
    location: str | None = Field(None, max_length=80)
    usage_status: str | None = Field(None, max_length=50)
    homelab_role: str | None = Field(None, max_length=100)
    host_name: str | None = Field(None, max_length=100)
    service_refs: list[str] | None = None
    purchase_date: date | None = None
    purchase_price: float | None = Field(None, ge=0)
    purchase_source: str | None = Field(None, max_length=100)
    purchase_url: str | None = Field(None, max_length=500)
    warranty_end: date | None = None
    estimated_resale_value: float | None = Field(None, ge=0)
    resale_confidence: str | None = Field(None, max_length=50)
    sell_decision: str | None = Field(None, max_length=50)
    sell_reason: str | None = Field(None, max_length=500)
    desired_min_profit: float | None = Field(None, ge=0)
    manual_pin: bool | None = None
    ebay_item_id: str | None = Field(None, max_length=100)
    ebay_watch_query: str | None = Field(None, max_length=200)
    external_refs: dict | None = None
    notes: str | None = Field(None, max_length=2000)


class ElectronicAssetOut(BaseModel):
    id: int
    name: str
    category: str | None
    brand: str | None
    model: str | None
    serial: str | None
    barcode: str | None
    condition: str
    status: str
    location: str
    usage_status: str
    homelab_role: str | None
    host_name: str | None
    service_refs: list[str]
    in_active_use: bool
    purchase_date: date | None
    purchase_price: float | None
    purchase_source: str | None
    purchase_url: str | None
    warranty_end: date | None
    estimated_resale_value: float | None
    market_value_eur: float | None = None
    market_value_at: datetime | None = None
    effective_market_value: float | None = None
    resale_confidence: str | None
    sell_decision: str
    sell_reason: str | None
    desired_min_profit: float | None
    manual_pin: bool
    estimated_profit: float | None = None
    ebay_item_id: str | None
    ebay_watch_query: str | None
    external_refs: dict = {}
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SellRecommendationOut(BaseModel):
    asset_id: int
    name: str
    decision: str
    reason: str
    purchase_price: float | None
    estimated_resale_value: float | None
    estimated_profit: float | None
    warranty_days_left: int | None = None
    ebay_watch_query: str | None = None
    usage_status: str | None = None
    homelab_role: str | None = None
    host_name: str | None = None


class MarketValueUpdateOut(BaseModel):
    asset_id: int
    market_value_eur: float | None
    market_value_at: datetime | None
    samples: int
    from_cache: bool


class PortfolioCategoryOut(BaseModel):
    category: str
    count: int
    market_value: float


class PortfolioResaleOut(BaseModel):
    asset_id: int
    name: str
    market_value_eur: float | None
    reason: str


class PortfolioOut(BaseModel):
    total_assets: int
    market_value_total: float
    valued_count: int
    purchase_total: float
    delta_vs_purchase: float
    delta_count: int
    categories: list[PortfolioCategoryOut]
    resale_recommendations: list[PortfolioResaleOut]
