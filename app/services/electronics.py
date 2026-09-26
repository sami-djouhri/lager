"""Electronic asset service: Einzelstuecke, eBay-Zeug, Verkaufskandidaten."""

from __future__ import annotations

from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.domain import DomainError
from app.models import ElectronicAsset
from app.schemas import ElectronicAssetCreate, ElectronicAssetUpdate


SELL_DECISIONS = {"behalten", "verkaufen", "pruefen", "teiletraeger", "entsorgen"}


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
        offset: int = 0,
        limit: int = 200,
    ) -> tuple[list[ElectronicAsset], int]:
        stmt = select(ElectronicAsset)
        if status:
            stmt = stmt.where(ElectronicAsset.status == status)
        if category:
            stmt = stmt.where(ElectronicAsset.category == category)
        if sell_decision:
            stmt = stmt.where(ElectronicAsset.sell_decision == sell_decision)
        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(or_(
                ElectronicAsset.name.ilike(pattern),
                ElectronicAsset.brand.ilike(pattern),
                ElectronicAsset.model.ilike(pattern),
                ElectronicAsset.serial.ilike(pattern),
                ElectronicAsset.ebay_watch_query.ilike(pattern),
            ))
        rows = list(self.db.execute(stmt.order_by(ElectronicAsset.name)).scalars().all())
        return rows[offset : offset + limit], len(rows)

    def get(self, asset_id: int) -> ElectronicAsset | None:
        return self.db.get(ElectronicAsset, asset_id)

    def create(self, data: ElectronicAssetCreate) -> ElectronicAsset:
        self._check_unique(serial=data.serial, barcode=data.barcode)
        asset = ElectronicAsset(
            name=data.name,
            category=data.category,
            brand=data.brand,
            model=data.model,
            serial=data.serial,
            barcode=data.barcode,
            condition=data.condition,
            status=data.status,
            location=data.location,
            usage_status=data.usage_status,
            homelab_role=data.homelab_role,
            host_name=data.host_name,
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
        asset.service_refs = data.service_refs
        self._apply_decision(asset)
        self.db.add(asset)
        self.db.flush()
        return asset

    def update(self, asset_id: int, data: ElectronicAssetUpdate) -> ElectronicAsset:
        asset = self.get(asset_id)
        if not asset:
            raise DomainError("Elektronik-Asset nicht gefunden", {"asset_id": asset_id})
        if data.serial is not None and data.serial != asset.serial:
            self._check_unique(serial=data.serial, barcode=None, current_id=asset_id)
            asset.serial = data.serial
        if data.barcode is not None and data.barcode != asset.barcode:
            self._check_unique(serial=None, barcode=data.barcode, current_id=asset_id)
            asset.barcode = data.barcode

        for field in (
            "name", "category", "brand", "model", "condition", "status", "location",
            "usage_status", "homelab_role", "host_name",
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
        if data.service_refs is not None:
            asset.service_refs = data.service_refs
        self._apply_decision(asset)
        self.db.flush()
        return asset

    def delete(self, asset_id: int) -> None:
        asset = self.get(asset_id)
        if not asset:
            raise DomainError("Elektronik-Asset nicht gefunden", {"asset_id": asset_id})
        self.db.delete(asset)
        self.db.flush()

    def sell_candidates(self) -> list[ElectronicAsset]:
        stmt = (
            select(ElectronicAsset)
            .where(
                ElectronicAsset.status == "aktiv",
                ElectronicAsset.sell_decision.in_(("verkaufen", "pruefen", "teiletraeger")),
            )
            .order_by(ElectronicAsset.sell_decision.desc(), ElectronicAsset.name)
        )
        return self.db.execute(stmt).scalars().all()

    def _check_unique(
        self,
        *,
        serial: str | None,
        barcode: str | None,
        current_id: int | None = None,
    ) -> None:
        for field, value in (("serial", serial), ("barcode", barcode)):
            if not value:
                continue
            column = getattr(ElectronicAsset, field)
            existing = self.db.execute(select(ElectronicAsset).where(column == value)).scalar_one_or_none()
            if existing and existing.id != current_id:
                raise DomainError(
                    f"{field} '{value}' ist bereits vergeben",
                    {"existing_id": existing.id, "field": field},
                )

    def _apply_decision(self, asset: ElectronicAsset) -> None:
        if asset.sell_decision not in SELL_DECISIONS:
            raise DomainError("Ungueltige Verkaufsentscheidung", {"sell_decision": asset.sell_decision})
        if asset.in_active_use:
            asset.sell_decision = "behalten"
            asset.sell_reason = f"Aktiv in Verwendung: {asset.usage_status}"
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
