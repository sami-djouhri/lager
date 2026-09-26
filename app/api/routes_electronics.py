"""Elektronik-/eBay-Asset routes."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.domain import DomainError
from app.models import ElectronicAsset
from app.schemas import (
    ElectronicAssetCreate,
    ElectronicAssetOut,
    ElectronicAssetUpdate,
    MarketValueUpdateOut,
    Page,
    PortfolioCategoryOut,
    PortfolioOut,
    PortfolioResaleOut,
    SellRecommendationOut,
)
from app.services.electronics import ElectronicAssetService
from app.services.homelab_inventory import seed_known_homelab_assets
from app.services.marktwatch import refresh_market_value

router = APIRouter(prefix="/api/electronics", tags=["electronics"])

MAX_PAGE_LIMIT = 500


def _asset_out(asset: ElectronicAsset) -> ElectronicAssetOut:
    return ElectronicAssetOut(
        id=asset.id,
        name=asset.name,
        category=asset.category,
        brand=asset.brand,
        model=asset.model,
        serial=asset.serial,
        barcode=asset.barcode,
        condition=asset.condition,
        status=asset.status,
        location=asset.location,
        usage_status=asset.usage_status,
        homelab_role=asset.homelab_role,
        host_name=asset.host_name,
        service_refs=asset.service_refs,
        in_active_use=asset.in_active_use,
        purchase_date=asset.purchase_date,
        purchase_price=asset.purchase_price,
        purchase_source=asset.purchase_source,
        purchase_url=asset.purchase_url,
        warranty_end=asset.warranty_end,
        estimated_resale_value=asset.estimated_resale_value,
        market_value_eur=asset.market_value_eur,
        market_value_at=asset.market_value_at,
        effective_market_value=asset.effective_market_value,
        resale_confidence=asset.resale_confidence,
        sell_decision=asset.sell_decision,
        sell_reason=asset.sell_reason,
        desired_min_profit=asset.desired_min_profit,
        manual_pin=bool(asset.manual_pin),
        estimated_profit=asset.estimated_profit,
        ebay_item_id=asset.ebay_item_id,
        ebay_watch_query=asset.ebay_watch_query,
        external_refs=asset.external_refs,
        notes=asset.notes,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )


def _sell_out(asset: ElectronicAsset) -> SellRecommendationOut:
    warranty_days_left = (asset.warranty_end - date.today()).days if asset.warranty_end else None
    return SellRecommendationOut(
        asset_id=asset.id,
        name=asset.name,
        decision=asset.sell_decision,
        reason=asset.sell_reason or "",
        purchase_price=asset.purchase_price,
        estimated_resale_value=asset.estimated_resale_value,
        estimated_profit=asset.estimated_profit,
        warranty_days_left=warranty_days_left,
        ebay_watch_query=asset.ebay_watch_query,
        usage_status=asset.usage_status,
        homelab_role=asset.homelab_role,
        host_name=asset.host_name,
    )


@router.get("", response_model=Page[ElectronicAssetOut])
def list_assets(
    q: str | None = None,
    status: str | None = None,
    category: str | None = None,
    sell_decision: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=MAX_PAGE_LIMIT),
    db: Session = Depends(get_db),
):
    svc = ElectronicAssetService(db)
    assets, total = svc.list_all(
        q=q,
        status=status,
        category=category,
        sell_decision=sell_decision,
        offset=offset,
        limit=limit,
    )
    return Page[ElectronicAssetOut](
        items=[_asset_out(a) for a in assets],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/sell-candidates", response_model=list[SellRecommendationOut])
def sell_candidates(db: Session = Depends(get_db)):
    svc = ElectronicAssetService(db)
    return [_sell_out(a) for a in svc.sell_candidates()]


@router.post("/homelab/seed-known", response_model=list[ElectronicAssetOut])
def seed_homelab_assets(db: Session = Depends(get_db)):
    assets = seed_known_homelab_assets(db)
    db.commit()
    for asset in assets:
        db.refresh(asset)
    return [_asset_out(a) for a in assets]


@router.get("/portfolio", response_model=PortfolioOut)
def portfolio(db: Session = Depends(get_db)):
    """Wertsachen-Portfolio: Kennzahlen + Kategorien + Verkaufsempfehlungen.

    Ersetzt die saganta assets-App (Super-App-Merge Phase 3). Marktwert =
    effective_market_value (marktwatch-Median, Fallback manueller Schätzwert).
    """
    svc = ElectronicAssetService(db)
    assets, _total = svc.list_all(offset=0, limit=MAX_PAGE_LIMIT)

    market_total = 0.0
    valued = 0
    purchase_total = 0.0
    delta = 0.0
    delta_count = 0
    cats: dict[str, PortfolioCategoryOut] = {}
    recs: list[PortfolioResaleOut] = []

    for a in assets:
        mv = a.effective_market_value
        if mv is not None:
            market_total += mv
            valued += 1
        if a.purchase_price is not None:
            purchase_total += a.purchase_price
        if mv is not None and a.purchase_price is not None:
            delta += mv - a.purchase_price
            delta_count += 1

        cat = a.category or "Ohne Kategorie"
        entry = cats.get(cat)
        if entry is None:
            entry = PortfolioCategoryOut(category=cat, count=0, market_value=0.0)
            cats[cat] = entry
        entry.count += 1
        entry.market_value += mv or 0.0

        # Empfehlung: nicht in aktiver Nutzung, nicht gepinnt, Wert über Threshold
        if (
            mv is not None
            and mv >= settings.RESALE_THRESHOLD_EUR
            and not a.in_active_use
            and not a.manual_pin
        ):
            recs.append(
                PortfolioResaleOut(
                    asset_id=a.id,
                    name=a.name,
                    market_value_eur=mv,
                    reason=a.sell_reason
                    or f"Marktwert {mv:.0f} EUR, nicht in aktiver Nutzung",
                )
            )

    recs.sort(key=lambda r: r.market_value_eur or 0, reverse=True)
    return PortfolioOut(
        total_assets=len(assets),
        market_value_total=round(market_total, 2),
        valued_count=valued,
        purchase_total=round(purchase_total, 2),
        delta_vs_purchase=round(delta, 2),
        delta_count=delta_count,
        categories=sorted(cats.values(), key=lambda c: c.category),
        resale_recommendations=recs,
    )


@router.post("/{asset_id}/refresh-market-value", response_model=MarketValueUpdateOut)
def refresh_asset_market_value(
    asset_id: int,
    force: bool = Query(False),
    db: Session = Depends(get_db),
):
    svc = ElectronicAssetService(db)
    asset = svc.get(asset_id)
    if not asset:
        raise DomainError("Elektronik-Asset nicht gefunden", {"asset_id": asset_id})
    result = refresh_market_value(asset, force=force)
    db.commit()
    db.refresh(asset)
    return MarketValueUpdateOut(
        asset_id=asset.id,
        market_value_eur=asset.market_value_eur,
        market_value_at=asset.market_value_at,
        samples=result.samples,
        from_cache=result.from_cache,
    )


@router.get("/{asset_id}", response_model=ElectronicAssetOut)
def get_asset(asset_id: int, db: Session = Depends(get_db)):
    svc = ElectronicAssetService(db)
    asset = svc.get(asset_id)
    if not asset:
        raise DomainError("Elektronik-Asset nicht gefunden", {"asset_id": asset_id})
    return _asset_out(asset)


@router.post("", response_model=ElectronicAssetOut, status_code=201)
def create_asset(body: ElectronicAssetCreate, db: Session = Depends(get_db)):
    svc = ElectronicAssetService(db)
    asset = svc.create(body)
    db.commit()
    db.refresh(asset)
    return _asset_out(asset)


@router.put("/{asset_id}", response_model=ElectronicAssetOut)
def update_asset(asset_id: int, body: ElectronicAssetUpdate, db: Session = Depends(get_db)):
    svc = ElectronicAssetService(db)
    asset = svc.update(asset_id, body)
    db.commit()
    db.refresh(asset)
    return _asset_out(asset)


@router.delete("/{asset_id}", status_code=204)
def delete_asset(asset_id: int, db: Session = Depends(get_db)):
    svc = ElectronicAssetService(db)
    svc.delete(asset_id)
    db.commit()
