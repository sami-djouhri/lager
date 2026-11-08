"""Electronic asset service: Einzelstuecke, eBay-Zeug, Verkaufskandidaten."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.domain import DomainError
from app.models import ABGAENGE, SHOPFLOOR_GRUENDE, VERBLEIB, Sache, Verlauf
from app.schemas import ElectronicAssetCreate, ElectronicAssetUpdate
from app.services.plaetze import PlatzService, protokolliere
from app.services.sachen import naechste_kennung


# usage_status vor 2026-11-01; jede aktive Stufe ist heute „Im Einsatz".
AKTIVE_ALTSTUFEN = {"critical", "homelab_active", "daily_use"}

SELL_DECISIONS = {"behalten", "verkaufen", "pruefen", "teiletraeger", "entsorgen"}


def verkauf_empfohlen(a: Sache) -> bool:
    """Lohnt der Verkauf: Wert ueber der Schwelle, nicht im Einsatz, nicht gepinnt.

    Eine Stelle fuer die Portfolio-Seite und den Satz der Startseite
    (`app/bereiche.py`), sonst nennen beide verschiedene Zahlen.
    """
    mv = a.effective_market_value
    return (
        mv is not None
        and mv >= settings.RESALE_THRESHOLD_EUR
        and not a.in_active_use
        and not a.manual_pin
    )


# Ab hier schlaegt das Lager vor, eine vermisste Sache als weg zu buchen
# (dieselbe Frist wie medien `dashboard.py`). Gebucht wird nie von selbst.
AUSBUCHEN_NACH_TAGEN = 30


def vermisst_seit(db: Session, sachen: list[Sache]) -> dict[int, datetime]:
    """Je vermisster Sache: wann sie zuletzt auf „vermisst" gesetzt wurde.

    Der juengste Eintrag mit genau diesem Wert, nicht der erste (Vorbild
    medien `logik.draussen_seit`): eine Sache, die schon einmal vermisst war und
    gefunden wurde, alterte sonst ab dem ersten Mal und stuende sofort zum
    Ausbuchen da. Ohne Verlaufseintrag kein Datum: ein geratenes saehe aus wie
    ein gemessenes.
    """
    offen = [s.id for s in sachen if s.verbleib == "vermisst" and s.id is not None]
    if not offen:
        return {}
    seit: dict[int, datetime] = {}
    for sid, am in db.execute(
        select(Verlauf.ziel_id, Verlauf.am).where(
            Verlauf.ziel == "sache", Verlauf.feld == "verbleib", Verlauf.neu == "vermisst",
            Verlauf.ziel_id.in_(offen),
        ).order_by(Verlauf.am, Verlauf.id)
    ).all():
        seit[sid] = am.replace(tzinfo=None) if am.tzinfo else am
    return seit


def lange_vermisst(seit: datetime | None, jetzt: datetime | None = None) -> bool:
    if seit is None:
        return False
    jetzt = jetzt or datetime.now(timezone.utc).replace(tzinfo=None)
    return (jetzt - seit).days >= AUSBUCHEN_NACH_TAGEN


def _ist_exemplar(asset: Sache) -> bool:
    # Spaet importiert wie in `_setze_verbleib`: app.bereiche liest diesen Dienst mit.
    from app.bereiche import EXEMPLAR, NACH_SCHLUESSEL

    b = NACH_SCHLUESSEL.get(asset.bereich or "")
    return b is not None and b.bauart == EXEMPLAR


class ElectronicAssetService:
    def __init__(self, db: Session):
        self.db = db

    def list_all(
        self,
        *,
        status: str | None = None,
        category: str | None = None,
        sell_decision: str | None = None,
        q: str | None = None,
        bereich: str = "technik",
        abgegangen: bool = False,
        offset: int = 0,
        limit: int = 200,
    ) -> tuple[list[Sache], int]:
        # Je Bereich, Vorgabe „Technik & Sachen": life-ops und die Lager-App
        # lesen /api/electronics ohne Parameter und sollen keine DVDs sehen.
        stmt = select(Sache).where(Sache.bereich == bereich)
        # Abgegangenes faellt aus jeder Liste (Stufe 7a); `abgegangen=True`
        # ist die Gegenliste „was hatte ich mal".
        stmt = stmt.where(Sache.abgang.is_not(None) if abgegangen else Sache.im_bestand())
        if status:
            stmt = stmt.where(Sache.status == status)
        if category:
            stmt = stmt.where(Sache.category == category)
        if sell_decision:
            stmt = stmt.where(Sache.sell_decision == sell_decision)
        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(or_(
                Sache.name.ilike(pattern),
                Sache.brand.ilike(pattern),
                Sache.model.ilike(pattern),
                Sache.serial.ilike(pattern),
                Sache.ebay_watch_query.ilike(pattern),
            ))
        rows = list(self.db.execute(stmt.order_by(Sache.name)).scalars().all())
        return rows[offset : offset + limit], len(rows)

    def get(self, asset_id: int) -> Sache | None:
        return self.db.get(Sache, asset_id)

    def create(self, data: ElectronicAssetCreate) -> Sache:
        self._check_unique(serial=data.serial)
        asset = Sache(
            bereich="technik",
            kennung=naechste_kennung(self.db),
            name=data.name,
            category=data.category,
            brand=data.brand,
            model=data.model,
            serial=data.serial,
            barcode=data.barcode,
            condition=data.condition,
            status=data.status,
            purchase_date=data.purchase_date,
            purchase_price=data.purchase_price,
            purchase_source=data.purchase_source,
            purchase_url=data.purchase_url,
            warranty_end=data.warranty_end,
            estimated_resale_value=data.estimated_resale_value,
            resale_confidence=data.resale_confidence,
            sell_decision=data.sell_decision,
            sell_reason=data.sell_reason,
            desired_min_profit=data.desired_min_profit,
            manual_pin=1 if data.manual_pin else 0,
            ebay_item_id=data.ebay_item_id,
            ebay_watch_query=data.ebay_watch_query,
            notes=data.notes,
        )
        asset.external_refs = data.external_refs
        asset.platz_id = self._platz_id(data.platz_id, data.location)
        grund = data.shopfloor_grund
        if grund is None and data.usage_status in AKTIVE_ALTSTUFEN:
            grund = "im_einsatz"
        # Eingebucht vor eingelagert: mit Platz und ohne Grund liegt sie dort,
        # sonst auf dem Shopfloor (ein Zugang bekommt nie von selbst einen Grund).
        if grund is not None:
            self._setze_verbleib(asset, "shopfloor", grund)
        elif asset.platz_id is not None:
            self._setze_verbleib(asset, "eingelagert", None)
        else:
            self._setze_verbleib(asset, "shopfloor", None)
        self._apply_decision(asset)
        self.db.add(asset)
        self.db.flush()
        return asset

    def update(self, asset_id: int, data: ElectronicAssetUpdate) -> Sache:
        asset = self.get(asset_id)
        if not asset:
            raise DomainError("Elektronik-Asset nicht gefunden", {"asset_id": asset_id})
        if asset.abgang is not None:
            # Sonst lagerte jemand eine verkaufte Sache wieder ein, ohne dass
            # sie in einer Liste auftaucht.
            raise DomainError(f"{asset.kennung} ist abgegangen. Erst den Abgang zurücknehmen.", {})
        gesetzt = data.model_fields_set
        if data.serial is not None and data.serial != asset.serial:
            self._check_unique(serial=data.serial, current_id=asset_id)
            asset.serial = data.serial
        if data.barcode is not None:
            asset.barcode = data.barcode

        for field in (
            "name", "category", "brand", "model", "condition", "status",
            "purchase_date", "purchase_price", "purchase_source", "purchase_url",
            "warranty_end", "estimated_resale_value", "resale_confidence",
            "sell_decision", "sell_reason", "desired_min_profit", "manual_pin", "ebay_item_id",
            "ebay_watch_query", "notes",
        ):
            value = getattr(data, field)
            if value is not None:
                setattr(asset, field, 1 if field == "manual_pin" and value else value)
        if data.external_refs is not None:
            asset.external_refs = data.external_refs
        for field in ("teil", "edition", "einband", "medium"):
            if field in gesetzt:
                if asset.bereich != "medien":
                    raise DomainError(f"„{field}“ gibt es nur bei Filme & Medien", {})
                neu = (getattr(data, field) or "").strip() or None
                if field == "medium" and neu is None:
                    raise DomainError("Ein Stück braucht ein Medium", {})
                protokolliere(self.db, "sache", asset.id, field, getattr(asset, field), neu)
                setattr(asset, field, neu)

        if "platz_id" in gesetzt or data.location is not None:
            neu = self._platz_id(data.platz_id, data.location)
            protokolliere(self.db, "sache", asset.id, "platz_id", asset.platz_id, neu)
            asset.platz_id = neu

        verbleib, grund = asset.verbleib, asset.shopfloor_grund
        if "shopfloor_grund" in gesetzt:
            verbleib, grund = "shopfloor", data.shopfloor_grund
        elif data.usage_status is not None:
            # Alte Form: aktiv = Im Einsatz, reserve = zurueck an den Platz.
            if data.usage_status in AKTIVE_ALTSTUFEN:
                verbleib, grund = "shopfloor", "im_einsatz"
            elif asset.in_active_use:
                verbleib = "eingelagert" if asset.platz_id is not None else "shopfloor"
                grund = None
        if data.verbleib is not None:
            verbleib = data.verbleib
            if verbleib == "eingelagert":
                grund = None
        elif "platz_id" in gesetzt and "shopfloor_grund" not in gesetzt \
                and asset.platz_id is not None and verbleib == "shopfloor" and grund is None:
            # Platz zugewiesen, nichts anderes gesagt: damit ist sie eingelagert.
            verbleib = "eingelagert"
        self._setze_verbleib(asset, verbleib, grund)
        self._apply_decision(asset)
        self.db.flush()
        return asset

    def delete(self, asset_id: int) -> None:
        asset = self.get(asset_id)
        if not asset:
            raise DomainError("Elektronik-Asset nicht gefunden", {"asset_id": asset_id})
        # Die Kennung bleibt im Verlauf und wird nie neu vergeben (ein Etikett klebt).
        protokolliere(self.db, "sache", asset.id, "geloescht", asset.kennung, None)
        self.db.delete(asset)
        self.db.flush()

    def abgang(self, asset_id: int, abgang: str, *, am: date | None = None,
               erloes: float | None = None, plattform: str | None = None,
               aus_medien: bool = False) -> Sache:
        """Verkauft oder Weg buchen (Stufe 7a). Die Zeile bleibt.

        Filme & Medien gehen in medien ab („der Verkauf bleibt in
        medien"); das Lager holt den Abgang dort ab (`aus_medien`). Ein Abgang
        hier von Hand stuende neben dem in medien und liefe auseinander.
        """
        asset = self.get(asset_id)
        if not asset:
            raise DomainError("Sache nicht gefunden", {"asset_id": asset_id})
        if abgang not in ABGAENGE:
            raise DomainError(f"Abgang '{abgang}' gibt es nicht", {"erlaubt": list(ABGAENGE)})
        if _ist_exemplar(asset) and not aus_medien:
            raise DomainError("Filme & Medien gehen in medien ab, dort verkaufen oder als weg "
                              "buchen. Das Lager übernimmt es beim nächsten Abgleich.", {})
        if asset.abgang is not None:
            raise DomainError(f"{asset.kennung} ist schon abgegangen", {"abgang": asset.abgang})
        if erloes is not None and abgang != "verkauft":
            raise DomainError("Einen Erlös gibt es nur bei „Verkauft“", {})
        protokolliere(self.db, "sache", asset.id, "abgang", None, abgang)
        asset.abgang = abgang
        asset.abgang_am = am or date.today()
        asset.erloes = erloes
        asset.abgang_plattform = (plattform or "").strip() or None
        self.db.flush()
        return asset

    def abgang_zuruecknehmen(self, asset_id: int) -> Sache:
        """Ein Abgang war ein Irrtum: die Sache steht wieder, wo sie vorher stand."""
        asset = self.get(asset_id)
        if not asset:
            raise DomainError("Sache nicht gefunden", {"asset_id": asset_id})
        if asset.abgang is None:
            raise DomainError(f"{asset.kennung} ist nicht abgegangen", {})
        if _ist_exemplar(asset):
            # Sonst holte der naechste Abgleich den Abgang aus medien gleich wieder.
            raise DomainError("Den Abgang eines Films nimmt man in medien zurück.", {})
        protokolliere(self.db, "sache", asset.id, "abgang", asset.abgang, None)
        asset.abgang = asset.abgang_am = asset.erloes = asset.abgang_plattform = None
        self.db.flush()
        return asset

    def sell_candidates(self) -> list[Sache]:
        stmt = (
            select(Sache)
            .where(
                Sache.im_bestand(),
                Sache.status == "aktiv",
                Sache.sell_decision.in_(("verkaufen", "pruefen", "teiletraeger")),
            )
            .order_by(Sache.sell_decision.desc(), Sache.name)
        )
        return self.db.execute(stmt).scalars().all()

    def _check_unique(self, *, serial: str | None, current_id: int | None = None) -> None:
        """Nur die Seriennummer ist eindeutig.

        Der Strichcode nicht mehr (seit 0009): er nennt die Sorte, und zwei
        gleiche Stuecke aus einem Konvolut tragen denselben.
        """
        if not serial:
            return
        existing = self.db.execute(select(Sache).where(Sache.serial == serial)).scalar_one_or_none()
        if existing and existing.id != current_id:
            raise DomainError(
                f"serial '{serial}' ist bereits vergeben",
                {"existing_id": existing.id, "field": "serial"},
            )

    def _platz_id(self, platz_id: int | None, location: str | None) -> int | None:
        svc = PlatzService(self.db)
        if platz_id is not None:
            return svc.get(platz_id).id
        platz = svc.aus_ortstext(location)
        return platz.id if platz else None

    def _setze_verbleib(self, asset: Sache, verbleib: str, grund: str | None) -> None:
        """Verliehen kommt mit Stufe 7b (nach Saganta Kontakte, RICHTUNG.md).

        Vermisst hat keinen Grund und behaelt den Platz: wird die Sache
        gefunden, sagt der Platz, wohin sie zurueckgehoert.
        """
        if verbleib not in VERBLEIB:
            raise DomainError(f"Verbleib '{verbleib}' gibt es (noch) nicht",
                              {"erlaubt": list(VERBLEIB)})
        if grund is not None and grund not in SHOPFLOOR_GRUENDE:
            raise DomainError(f"Unbekannter Shopfloor-Grund '{grund}'",
                              {"erlaubt": list(SHOPFLOOR_GRUENDE)})
        # Spaet importiert: app.bereiche liest ueber die Saetze diesen Dienst mit.
        from app.bereiche import gruende_fuer

        erlaubt = gruende_fuer(asset.bereich or "technik")
        if grund is not None and grund not in erlaubt:
            raise DomainError(
                f"„{SHOPFLOOR_GRUENDE[grund]}“ gibt es in diesem Bereich nicht",
                {"erlaubt": list(erlaubt)},
            )
        if verbleib == "vermisst":
            grund = None
        if verbleib == "eingelagert":
            if asset.platz_id is None:
                raise DomainError("Zum Einlagern fehlt der Platz", {"asset_id": asset.id})
            grund = None
        if asset.id is not None:
            protokolliere(self.db, "sache", asset.id, "verbleib", asset.verbleib, verbleib)
            protokolliere(self.db, "sache", asset.id, "shopfloor_grund",
                          asset.shopfloor_grund, grund)
        asset.verbleib = verbleib
        asset.shopfloor_grund = grund

    def _apply_decision(self, asset: Sache) -> None:
        if asset.sell_decision not in SELL_DECISIONS:
            raise DomainError("Ungueltige Verkaufsentscheidung", {"sell_decision": asset.sell_decision})
        if asset.in_active_use:
            asset.sell_decision = "behalten"
            asset.sell_reason = "Im Einsatz"
            return
        if asset.manual_pin:
            asset.sell_decision = "behalten"
            if not asset.sell_reason:
                asset.sell_reason = "Manuell gepinnt"
            return
        if asset.sell_decision != "behalten":
            return
        if asset.estimated_profit is not None:
            threshold = asset.desired_min_profit if asset.desired_min_profit is not None else 5.0
            if asset.estimated_profit >= threshold:
                asset.sell_decision = "verkaufen"
                asset.sell_reason = f"Gewinnziel erreicht ({asset.estimated_profit:.2f} EUR)"
            elif asset.estimated_profit < 0:
                asset.sell_decision = "pruefen"
                asset.sell_reason = f"Negativer erwarteter Gewinn ({asset.estimated_profit:.2f} EUR)"
        if asset.warranty_end and asset.warranty_end < date.today() and asset.sell_decision == "behalten":
            asset.sell_decision = "pruefen"
            asset.sell_reason = "Garantie abgelaufen"
