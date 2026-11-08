"""ORM models: Product, StockEntry, ConsumptionEvent, Platz, Sache, Verlauf, Einkauf."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
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
    # Bereich aus app/bereiche.py (nur Bauart „vorrat"). Altbestand = Lebensmittel.
    bereich: Mapped[str] = mapped_column(
        String(20), nullable=False, default="lebensmittel", server_default="lebensmittel",
        index=True,
    )
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
    # Lagerplatz; leer = Shopfloor, noch nicht eingelagert (RICHTUNG.md: Vorrat
    # kennt nur Platz oder Shopfloor, Verliehen und Vermisst gibt es nur fuer Sachen).
    platz_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("platz.id"), nullable=True, index=True
    )
    lot_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Was die eingebuchte Menge gekostet hat (Owner 2026-11-01: Einzelpreis
    # freiwillig, nie aus dem Gesamtbetrag verteilt). `eingangsmenge` haelt
    # die Menge beim Einbuchen fest: `quantity` sinkt mit jedem Verbrauch, und
    # ohne sie liesse sich spaeter kein Preis je Einheit und kein Verlust in
    # Euro rechnen.
    preis: Mapped[float | None] = mapped_column(Float, nullable=True)
    eingangsmenge: Mapped[float | None] = mapped_column(Float, nullable=True)
    einkauf_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("einkauf.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )
    opened_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    product: Mapped[Product] = relationship("Product", back_populates="stock_entries")
    platz: Mapped[Platz | None] = relationship("Platz")
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
# Platz – Raum › Regal › Fach › Kiste, mit Etikett
# ---------------------------------------------------------------------------

class Platz(Base):
    """Ein Lagerplatz. Die Verschachtelung ist fest (`app/services/plaetze.py`).

    `kennung` (`L-001`) steht auf dem Etikett und wird nie neu vergeben,
    auch nicht nach dem Loeschen: ein Etikett klebt, und ein altes Etikett,
    das auf einen neuen Platz zeigt, raeumt Dinge ins falsche Fach.
    """

    __tablename__ = "platz"
    __table_args__ = (UniqueConstraint("owner_sub", "kennung", name="uq_platz_owner_kennung"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_sub: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True, server_default=_OWNER
    )
    kennung: Mapped[str] = mapped_column(String(12), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    art: Mapped[str] = mapped_column(String(10), nullable=False)
    eltern_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("platz.id"), nullable=True, index=True
    )
    # Nur Kisten: was drin ist (Kleidung und Saison fuehren keine Einzelstuecke)
    # und optional der Bereich, zu dem die Kiste gehoert.
    inhalt: Mapped[str | None] = mapped_column(Text, nullable=True)
    bereich: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    eltern: Mapped[Platz | None] = relationship("Platz", remote_side="Platz.id")


# ---------------------------------------------------------------------------
# Sache – alles, was kein Vorrat ist (Technik-Stuecke, spaeter Werkstatt)
# ---------------------------------------------------------------------------

VERBLEIB = ("eingelagert", "shopfloor", "vermisst")
# Abgang einer Sache (Stufe 7a, Owner wie in medien: „verschenkt, entsorgt und
# verloren ist dasselbe = weg"). Die Zeile bleibt, sie faellt nur aus den Listen.
ABGAENGE = {"verkauft": "Verkauft", "weg": "Weg"}
# Zustand einer Sache, EINE Skala fuer alle Bereiche (Owner 2026-11-01, Stufe 5):
# die von medien plus „Neu". Bei Doppelten entscheidet er im Lagern-Lauf, welches
# Stueck gemeint ist (medien `_artikel_waehlen`), und medien rechnet mit genau
# diesen Werten seine Dubletten-Regel.
ZUSTAENDE = ("Neu", "Sehr gut", "Gut", "Gebraucht", "Beschädigt", "Ungeprüft")
# Alle Gruende; welcher in welchem Bereich gilt, steht in `app/bereiche.py`
# (Owner 2026-11-01: je Bereich, Filme mit Rippen und Schauen wie in medien).
SHOPFLOOR_GRUENDE = {
    "im_einsatz": "Im Einsatz",
    "reparatur": "In Reparatur",
    "verkauf_vorbereiten": "Verkauf vorbereiten",
    "rippen": "Rippen",
    "schauen": "Schauen",
}


class Sache(Base):
    """Eine Sache: ein Ding, eine Zeile (bis 2026-11-01 `electronic_asset`).

    Lagerplatz und Verbleib sind zwei Dinge (Vorbild medien): `platz_id`
    sagt, wohin die Sache gehoert, und bleibt beim Herausholen stehen;
    `verbleib` sagt, wo sie ist. Auf dem Shopfloor heisst ein leerer Grund
    „noch nicht eingelagert"; „Im Einsatz" ist der Verkaufsschutz.
    """

    __tablename__ = "sache"
    # Der Strichcode ist NICHT eindeutig (seit 0009): er nennt die Sorte,
    # nicht das Stueck. Das Stueck ist die Kennung `S-0001` auf dem Etikett;
    # die Seriennummer bleibt eindeutig, weil sie genau ein Geraet meint.
    __table_args__ = (
        UniqueConstraint("owner_sub", "serial", name="uq_sache_owner_serial"),
        UniqueConstraint("owner_sub", "kennung", name="uq_sache_owner_kennung"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_sub: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True, server_default=_OWNER
    )
    bereich: Mapped[str] = mapped_column(
        String(20), nullable=False, default="technik", server_default="technik", index=True
    )
    # Fortlaufend je Mandant, nie neu vergeben (`app/services/sachen.py`).
    kennung: Mapped[str] = mapped_column(String(12), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(150), nullable=True)
    serial: Mapped[str | None] = mapped_column(String(150), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    # Nur Filme & Medien (Bauart `exemplar`, Stufe 5): der Titel lebt im
    # medien-Katalog, hier stehen seine Nummer und was das Stueck selbst ist.
    # `name` traegt eine Kopie des Katalogtitels zur Anzeige.
    titel_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    teil: Mapped[str | None] = mapped_column(String(80), nullable=True)
    edition: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # Nur Buecher: Hardcover, Taschenbuch … (seit 0013, `EINBAENDE` als Vorschlag).
    einband: Mapped[str | None] = mapped_column(String(30), nullable=True)
    medium: Mapped[str | None] = mapped_column(String(30), nullable=True)
    medientyp: Mapped[str | None] = mapped_column(String(30), nullable=True)
    titel_huelle: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Dateiname in der Foto-Ablage (`app/services/fotos.py`), kein Pfad.
    foto: Mapped[str | None] = mapped_column(String(80), nullable=True)
    einkauf_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("einkauf.id"), nullable=True, index=True
    )

    condition: Mapped[str] = mapped_column(String(30), default="Gut", index=True)
    status: Mapped[str] = mapped_column(String(30), default="aktiv", index=True)
    platz_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("platz.id"), nullable=True, index=True
    )
    verbleib: Mapped[str] = mapped_column(
        String(20), nullable=False, default="shopfloor", server_default="shopfloor", index=True
    )
    shopfloor_grund: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Abgegangen (Stufe 7a): `abgang` gesetzt heisst „nicht mehr im Haus".
    # Jede Liste filtert mit `Sache.im_bestand()`; `verbleib` und `platz_id`
    # bleiben stehen, damit ein Zuruecknehmen den Stand vorher wiederfindet.
    abgang: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    abgang_am: Mapped[date | None] = mapped_column(Date, nullable=True)
    erloes: Mapped[float | None] = mapped_column(Float, nullable=True)
    abgang_plattform: Mapped[str | None] = mapped_column(String(60), nullable=True)

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

    platz: Mapped[Platz | None] = relationship("Platz")

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

    @classmethod
    def im_bestand(cls):
        """Filter fuer jede Liste: nur, was nicht abgegangen ist."""
        return cls.abgang.is_(None)

    @property
    def in_active_use(self) -> bool:
        return self.verbleib == "shopfloor" and self.shopfloor_grund == "im_einsatz"

    @property
    def usage_status(self) -> str:
        # Fuer /api/electronics (life-ops, Lager-App): die alte Form, aus dem
        # Verbleib abgeleitet. Die alten Stufen critical/homelab_active sind in
        # „Im Einsatz" aufgegangen (Owner 2026-11-01).
        return "daily_use" if self.in_active_use else "reserve"

    @property
    def effective_market_value(self) -> float | None:
        # Marktwert (live) gewinnt, manueller Schätzwert ist Fallback.
        if self.market_value_eur is not None:
            return self.market_value_eur
        return self.estimated_resale_value


# ---------------------------------------------------------------------------
# Verlauf – jede Aenderung Feld fuer Feld
# ---------------------------------------------------------------------------

class Verlauf(Base):
    """Was sich wann geaendert hat, je Feld (Vorbild medien).

    Daraus kommen spaeter Alterung („seit 40 Tagen verliehen") und die
    Mahnliste, nicht aus einem Datumsfeld an der Sache. Ein geloeschter Platz
    hinterlaesst hier seine Kennung (`feld="geloescht"`), damit sie nie neu
    vergeben wird.
    """

    __tablename__ = "verlauf"
    __table_args__ = (Index("ix_verlauf_ziel", "ziel", "ziel_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_sub: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True, server_default=_OWNER
    )
    # "sache", "posten" oder "platz"; bewusst kein Fremdschluessel, der Verlauf
    # ueberlebt das, worueber er berichtet.
    ziel: Mapped[str] = mapped_column(String(10), nullable=False)
    ziel_id: Mapped[int] = mapped_column(Integer, nullable=False)
    feld: Mapped[str] = mapped_column(String(30), nullable=False)
    alt: Mapped[str | None] = mapped_column(Text, nullable=True)
    neu: Mapped[str | None] = mapped_column(Text, nullable=True)
    am: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), server_default=func.now(),
        index=True,
    )


# ---------------------------------------------------------------------------
# Einkauf – ein Einbuch-Lauf mit Gesamtbetrag und Laden
# ---------------------------------------------------------------------------

class Einkauf(Base):
    """Was ein Einbuch-Lauf gekostet hat (Stufe 4, Owner 2026-11-01).

    Bei Vorraeten wird der Gesamtbetrag **nicht** verteilt: 1 kg Mehl und
    200 g Kaese nach Menge gewichtet ergaeben ausgedachte Einzelpreise. Er
    beantwortet „was kostete der Einkauf", die Einzelpreise am Posten den Rest.
    Bei Sachen verteilt der Lauf den Betrag auf die Stuecke ohne eigenen Preis
    (`app/services/laeufe.py`).
    """

    __tablename__ = "einkauf"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_sub: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True, server_default=_OWNER
    )
    bereich: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    am: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    laden: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Eine der Ketten aus app/ketten.py, leer = Sonstiger (Preisvergleich Stufe 1).
    kette: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    gesamt: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )
