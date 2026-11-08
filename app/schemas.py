"""Pydantic In/Out schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Generic, Literal, TypeVar

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
    bereich: str = Field("lebensmittel", max_length=20)
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
    bereich: str | None = Field(None, max_length=20)
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
    bereich: str = "lebensmittel"
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
    # Lagerplatz; ohne beides liegt der Posten auf dem Shopfloor. `location`
    # ist der alte Ortstext (Lager-App 0.1.0) und wird auf einen Platz gelegt,
    # siehe `PlatzService.aus_ortstext`. `platz_id` gewinnt.
    platz_id: int | None = None
    location: str | None = Field(None, max_length=50)
    lot_note: str | None = Field(None, max_length=200)
    # Was die ganze eingebuchte Menge gekostet hat, freiwillig.
    preis: float | None = Field(None, ge=0, le=1_000_000)

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
    # `platz_id: null` ausdruecklich gesetzt = zurueck auf den Shopfloor.
    platz_id: int | None = None
    location: str | None = Field(None, max_length=50)
    lot_note: str | None = Field(None, max_length=200)
    opened_at: date | None = None
    # `preis: null` ausdruecklich gesetzt = Preis entfernen.
    preis: float | None = Field(None, ge=0, le=1_000_000)

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
    # Name des Platzes, „nicht eingelagert" ohne Platz (alte Form, nie leer).
    location: str
    platz_id: int | None = None
    platz_kennung: str | None = None
    platz_pfad: str = ""
    days_until_expiry: int | None = None
    opened_at: date | None = None
    preis: float | None = None
    eingangsmenge: float | None = None
    einkauf_id: int | None = None

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


class AusbuchenSammelRequest(BaseModel):
    """Mehrere Posten ganz ausbuchen (Mehrfachauswahl im Bestand).

    Anders als `/consume` nennt der Aufruf Posten statt einer Menge je Produkt:
    wer drei abgelaufene Joghurts waehlt, meint genau diese drei und nicht die
    drei mit dem aeltesten MHD.
    """

    entry_ids: list[int] = Field(min_length=1, max_length=500)
    reason: Literal["verbraucht", "weggeworfen", "abgelaufen"] = "abgelaufen"
    source: str = Field("manual", max_length=50)


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


class CategoryUnitWaste(BaseModel):
    """Verlustrechnung je Einheit: Mengen sind nur innerhalb einer Einheit addierbar."""

    unit: str
    consumed: float
    discarded: float
    waste_percent: float


class CategoryAnalyticsItem(BaseModel):
    """Kategoriesicht auf Verlust.

    Die Felder heissen seit dem 2026-10-24 anders als vorher, weil sich ihre
    Bedeutung geaendert hat: ``total_consumed`` summierte Gramm, Milliliter und
    Stueck zu einer Zahl und ``waste_percent`` kam aus einem Verhaeltnis von
    Anzahl zu Menge. Ein gleich benanntes Feld mit anderer Rechnung dahinter
    waere die schlechtere Wahl gewesen -- niemand prueft ein Feld nach, das es
    schon gab. Rechenweg und Belege: ``StatsService.get_category_analytics``.

    ``waste_percent`` traegt die Quote der Einheit mit der groessten Bewegung,
    ``waste_unit`` nennt sie. Ohne Buchung im Fenster ist die Quote 0.0 und
    ``waste_unit`` None -- das unterscheidet "nichts weggeworfen" von "nichts
    gemessen".
    """

    category: str
    active_items: int
    expired_in_stock: int
    waste_percent: float
    waste_unit: str | None = None
    events_total: int
    events_discarded: int
    by_unit: list[CategoryUnitWaste] = []


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
    # low_stock | weekly_average | expired | expiring_soon
    # `expired` kam am 2026-10-24 dazu. Vorher trug abgelaufene Ware das
    # Etikett `expiring_soon`, siehe ShoppingService._expiring_products.
    reason: str
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
    condition: str = Field("Gut", max_length=50)
    status: str = Field("aktiv", max_length=50)
    platz_id: int | None = None
    # Alte Formen: Ortstext wird ein Platz, ein aktiver usage_status wird
    # Shopfloor-Grund „Im Einsatz". `shopfloor_grund` gewinnt.
    location: str | None = Field(None, max_length=80)
    usage_status: str | None = Field(None, max_length=50)
    shopfloor_grund: str | None = Field(None, max_length=30)
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
    # Nur ausdruecklich gesetzte Felder wirken (`model_fields_set`), damit
    # `platz_id: null` und `shopfloor_grund: null` etwas bedeuten koennen.
    platz_id: int | None = None
    verbleib: str | None = Field(None, max_length=20)
    shopfloor_grund: str | None = Field(None, max_length=30)
    location: str | None = Field(None, max_length=80)
    usage_status: str | None = Field(None, max_length=50)
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
    # Nur Filme & Medien (Quittung im Einbuch-Lauf): ausdruecklich leer
    # geschickt heisst geleert, wie bei `platz_id`.
    teil: str | None = Field(None, max_length=80)
    edition: str | None = Field(None, max_length=80)
    einband: str | None = Field(None, max_length=30)
    medium: str | None = Field(None, max_length=30)


class AbgangIn(BaseModel):
    """Verkauft oder Weg (Stufe 7a). Ohne Datum gilt heute."""

    abgang: str = Field(..., max_length=20)
    am: date | None = None
    erloes: float | None = Field(None, ge=0)
    plattform: str | None = Field(None, max_length=60)


class ElectronicAssetOut(BaseModel):
    id: int
    kennung: str = ""
    name: str
    # Nur Filme & Medien
    titel_id: int | None = None
    teil: str | None = None
    edition: str | None = None
    einband: str | None = None
    medium: str | None = None
    medientyp: str | None = None
    category: str | None
    brand: str | None
    model: str | None
    serial: str | None
    barcode: str | None
    condition: str
    status: str
    bereich: str = "technik"
    location: str
    platz_id: int | None = None
    platz_kennung: str | None = None
    platz_pfad: str = ""
    verbleib: str
    shopfloor_grund: str | None = None
    # Stufe 7a: gesetzt nur in der Liste der Abgaenge (`?abgegangen=true`)
    abgang: str | None = None
    abgang_am: date | None = None
    erloes: float | None = None
    abgang_plattform: str | None = None
    # Nur bei Vermisstem: seit wann (aus dem Verlauf) und ob das Lager das
    # Ausbuchen vorschlaegt (`AUSBUCHEN_NACH_TAGEN`). Gebucht wird nie von selbst.
    vermisst_seit: datetime | None = None
    ausbuchen_vorschlagen: bool = False
    usage_status: str
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
    # Dateiname des Fotos (wechselt mit jedem neuen Bild, taugt als Cache-Schluessel).
    foto: str | None = None
    einkauf_id: int | None = None
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


# ---------------------------------------------------------------------------
# Bereiche (Startseite)
# ---------------------------------------------------------------------------

class BereichSatzOut(BaseModel):
    # Fester Schluessel je Satzart (vorbei/bald/knapp/ruhig/leer/verkauf/stufe):
    # Tests vergleichen ihn statt des Wortlauts.
    schluessel: str
    text: str
    anzahl: int = 0
    blockiert: bool = False


class GrundOut(BaseModel):
    schluessel: str
    name: str


class BereichOut(BaseModel):
    schluessel: str
    name: str
    bauart: str
    frist: str | None = None
    orte: list[str] = []
    kategorien: list[str] = []
    bereit: bool
    # Shopfloor-Gruende des Bereichs (nur Sachen-Bereiche).
    gruende: list[GrundOut] = []
    satz: BereichSatzOut
    titel_verweis: str | None = None


# ---------------------------------------------------------------------------
# Plaetze und Shopfloor
# ---------------------------------------------------------------------------

class PlatzCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    art: str = Field(..., max_length=10)
    eltern_id: int | None = None
    inhalt: str | None = Field(None, max_length=2000)
    bereich: str | None = Field(None, max_length=20)


class PlatzUpdate(BaseModel):
    # Nur ausdruecklich gesetzte Felder wirken; `eltern_id` = umziehen.
    name: str | None = Field(None, max_length=120)
    eltern_id: int | None = None
    inhalt: str | None = Field(None, max_length=2000)
    bereich: str | None = Field(None, max_length=20)


class PlatzOut(BaseModel):
    id: int
    kennung: str
    name: str
    art: str
    eltern_id: int | None
    pfad: str
    inhalt: str | None = None
    bereich: str | None = None
    kinder: int = 0
    posten: int = 0
    sachen: int = 0


class PlatzDingOut(BaseModel):
    """Ein Ding an einem Platz oder auf dem Shopfloor: Posten oder Sache."""
    art: str  # "posten" oder "sache"
    id: int
    name: str
    bereich: str
    detail: str = ""
    platz_id: int | None = None
    platz_pfad: str = ""
    shopfloor_grund: str | None = None
    # Nur an Sachen: Etikett-Kennung `S-0001` und ob ein Foto da ist.
    kennung: str | None = None
    foto: str | None = None
    # Nur an Sachen: eingelagert, shopfloor oder vermisst (Stufe 7a).
    verbleib: str | None = None
    mhd: date | None = None


class SucheOut(BaseModel):
    """„Wo ist …" (`/api/suche`): Dinge und Plaetze, beide gekappt; `mehr` sagt, dass es weitergeht."""
    q: str
    dinge: list[PlatzDingOut]
    plaetze: list[PlatzOut]
    mehr: bool = False


class PlatzInhaltOut(BaseModel):
    platz: PlatzOut
    unterplaetze: list[PlatzOut]
    dinge: list[PlatzDingOut]


class ShopfloorGruppeOut(BaseModel):
    # Schluessel des Grundes, None = noch nicht eingelagert
    grund: str | None
    name: str
    dinge: list[PlatzDingOut]


class ShopfloorOut(BaseModel):
    gruppen: list[ShopfloorGruppeOut]
    anzahl: int


# ---------------------------------------------------------------------------
# Laeufe: Einbuchen, Lagern, Abschluss (Stufe 4)
# ---------------------------------------------------------------------------

class EinbuchenIn(BaseModel):
    """Ein Schritt im Einbuch-Lauf. Die Vorgabe (Platz, Zustand) gilt je Durchgang
    und kommt bei jedem Schritt mit; der Lauf selbst lebt im Browser."""
    bereich: str = Field(..., max_length=20)
    code: str | None = Field(None, max_length=150)
    # Name, wenn der Strichcode unbekannt ist oder es keinen gibt.
    name: str | None = Field(None, max_length=200)
    # Sachen: „bekannt" gesehen und trotzdem ein neues Stueck.
    bestaetigt: bool = False
    platz_id: int | None = None
    zustand: str | None = Field(None, max_length=30)
    # Vorrat: welche Posten dieser Lauf schon angelegt hat. Ein zweiter Scan
    # desselben Produkts mit gleichem MHD erhoeht dort die Menge (Owner: ein
    # Posten je MHD).
    lauf_posten: list[int] = Field(default_factory=list, max_length=2000)
    preis: float | None = Field(None, ge=0, le=1_000_000)
    # Vorrat: Antwort auf `menge_fehlt`, sonst leer (Packungsgroesse gewinnt).
    menge: float | None = Field(None, gt=0, le=1_000_000)
    einheit: str | None = Field(None, max_length=20)
    mhd: date | None = None
    # Kategorie aus dem Vorschlag (OpenFoodFacts) beim Anlegen eines Produkts.
    kategorie: str | None = Field(None, max_length=100)
    # Filme & Medien: gewaehlter Katalogtitel (sonst wird `name` in medien
    # gesucht bzw. angelegt), Vorgabe je Durchgang und was die Huelle sagt.
    titel_id: int | None = None
    # Der Katalogtitel zu `titel_id` (aus der Suche), `name` bleibt die Huelle.
    katalogtitel: str | None = Field(None, max_length=200)
    medium: str | None = Field(None, max_length=30)
    medientyp: str | None = Field(None, max_length=30)
    teil: str | None = Field(None, max_length=80)
    edition: str | None = Field(None, max_length=80)


class VorschlagOut(BaseModel):
    name: str
    category: str | None = None
    quelle: str


class EinbuchenOut(BaseModel):
    # neu | mehr | bekannt | name_fehlt | wiedergesehen
    art: str
    posten: StockEntryOut | None = None
    sache: ElectronicAssetOut | None = None
    vorhanden: list[ElectronicAssetOut] = []
    vorschlag: VorschlagOut | None = None
    produkt_neu: bool = False
    # Wenn das Produkt in einem anderen Bereich gefuehrt wird als dem des Laufs.
    anderer_bereich: str | None = None
    code: str | None = None
    # Bei `menge_fehlt`: zu welchem Produkt die Menge fehlt
    produkt_id: int | None = None
    produkt_name: str | None = None
    produkt_einheit: str | None = None
    # Filme & Medien: medien war beim Einbuchen nicht erreichbar, der Titel
    # wird nachgetragen, sobald es wieder antwortet.
    titel_offen: bool = False
    # Bei `name_fehlt` nach einem Buch-Scan: warum die ISBN keinen Titel ergab.
    hinweis: str | None = None


class LagernIn(BaseModel):
    # ein = nur Offenes einlagern, um = Eingelagertes umziehen, aus = auf den Shopfloor
    richtung: str = Field(..., max_length=3)
    code: str = Field(..., min_length=1, max_length=150)
    platz_id: int | None = None
    grund: str | None = Field(None, max_length=30)
    # Antwort auf eine Rueckfrage: MHD (Vorrat) oder Zustand (Sachen).
    mhd: date | None = None
    # Antwort „ohne MHD" auf die MHD-Rueckfrage (ein leeres `mhd` heisst „nicht gefragt").
    ohne_mhd: bool = False
    zustand: str | None = Field(None, max_length=30)


class LagernOut(BaseModel):
    # platz | gebucht | welches | unbekannt
    art: str
    platz: PlatzOut | None = None
    ding: PlatzDingOut | None = None
    vorher_pfad: str = ""
    # Rueckfrage: welche MHDs bzw. Zustaende zur Wahl stehen
    mhds: list[date | None] = []
    zustaende: list[str] = []
    # Rueckfrage `grund_fehlt`: die Gruende aus dem Bereich des Stuecks
    gruende: list[str] = []
    bereich: str | None = None
    hinweis: str | None = None
    # Stand vor der Buchung, damit die Quittung sie zuruecknehmen kann.
    vorher_platz_id: int | None = None
    vorher_verbleib: str | None = None
    vorher_grund: str | None = None


class ZuruecknehmenIn(BaseModel):
    """Eine Quittungszeile zuruecknehmen: genau eins von `posten_id` und `sache_id`.

    Im Lagern-Lauf kommt der Stand vor der Buchung mit (`vorher_*` aus
    `LagernOut`); im Einbuch-Lauf heisst Zuruecknehmen, dass das Ding wieder geht.
    """
    posten_id: int | None = None
    sache_id: int | None = None
    vorher_platz_id: int | None = None
    vorher_verbleib: str | None = Field(None, max_length=20)
    vorher_grund: str | None = Field(None, max_length=30)


class ZuruecknehmenOut(BaseModel):
    text: str
    ding: PlatzDingOut | None = None


class AbschlussIn(BaseModel):
    bereich: str = Field(..., max_length=20)
    posten: list[int] = Field(default_factory=list, max_length=2000)
    sachen: list[int] = Field(default_factory=list, max_length=2000)
    gesamt: float | None = Field(None, gt=0, le=1_000_000)
    laden: str | None = Field(None, max_length=100)
    # Eine der Ketten aus app/ketten.py (Logo antippen); leer = Sonstiger,
    # dann zaehlt ein Freitext mit Kettennamen trotzdem fuer die Kette.
    kette: str | None = Field(None, max_length=20)
    am: date | None = None


class EinkaufOut(BaseModel):
    id: int
    bereich: str
    am: date
    laden: str | None
    kette: str | None = None
    gesamt: float | None
    posten: int = 0
    sachen: int = 0
    # Summe der Einzelpreise und wie viele Dinge keinen haben
    einzelpreise: float = 0.0
    ohne_preis: int = 0
    # Sachen: verteilter Anteil je Sache (id -> Euro)
    verteilt: dict[int, float] = {}


class TitelTrefferOut(BaseModel):
    """Ein Titel aus dem medien-Katalog (Suche im Einbuch-Lauf)."""
    id: int
    titel: str
    medientyp: str | None = None
    jahr: str | None = None
