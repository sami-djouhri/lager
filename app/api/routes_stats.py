"""Stats routes: consumption analytics, expiry forecast, waste summary."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.domain import DomainError
from app.schemas import (
    CategoryAnalyticsItem,
    ConsumptionByProduct,
    ExpiryForecastItem,
    LowStockItem,
    TurnoverResult,
    WasteSummary,
)
from app.services.stats import StatsService

router = APIRouter(prefix="/api/stats", tags=["stats"])
critical_router = APIRouter(tags=["stats"])


@router.get("/consumption", response_model=list[ConsumptionByProduct])
def consumption_stats(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    svc = StatsService(db)
    return svc.consumption_by_product(days=days)


@router.get("/waste", response_model=WasteSummary)
def waste_stats(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    svc = StatsService(db)
    return svc.waste_summary(days=days)


@router.get("/expiry-forecast", response_model=list[ExpiryForecastItem])
def expiry_forecast(db: Session = Depends(get_db)):
    svc = StatsService(db)
    return svc.expiry_forecast()


@router.get("/categories", response_model=list[CategoryAnalyticsItem])
def category_analytics(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    svc = StatsService(db)
    return svc.get_category_analytics(days=days)


@router.get("/low-stock", response_model=list[LowStockItem])
def low_stock(threshold_pct: int = Query(100, ge=1, le=100), db: Session = Depends(get_db)):
    svc = StatsService(db)
    return svc.low_stock(threshold_pct=threshold_pct)


@critical_router.get("/api/critical")
def critical_stock(db: Session = Depends(get_db)):
    svc = StatsService(db)
    return {"critical": svc.critical_stock()}


MAX_TURNOVER_IDS = 500


@router.get("/turnover", response_model=list[TurnoverResult])
def turnover_rates(
    product_ids: str | None = Query(
        None,
        description=(
            "Kommaliste von Produkt-Nummern. Weggelassen = alle Produkte mit "
            "Verbrauch im Zeitraum."
        ),
    ),
    days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Verbrauchsraten in einem Abruf statt einem je Produkt.

    ★ Gegenstueck zu ``/turnover/{product_id}``, angelegt am 2026-09-13, weil
    mealprep die Einzelauskunft in einer Schleife rief: 14 Anfragen fuer ein
    Dashboard bei einem Deckel von 60 je Minute. Wer hier fragt, bezahlt eine.

    Produkte ohne Verbrauch im Zeitraum fehlen in der Antwort. Das ist der
    Unterschied zwischen "gemessen, keine Bewegung" und "nicht gemessen": eine
    Antwort mit weniger Zeilen ist eine Messung, ein Fehlschlag ist ein
    Fehlerstatus. Wer beides gleich behandelt, baut sich Nullen, die wie Daten
    aussehen.
    """
    ids: list[int] | None = None
    if product_ids is not None:
        roh = [teil.strip() for teil in product_ids.split(",") if teil.strip()]
        try:
            ids = [int(teil) for teil in roh]
        except ValueError:
            raise DomainError(
                "product_ids muss eine Kommaliste von Zahlen sein",
                {"product_ids": product_ids},
            ) from None
        if len(ids) > MAX_TURNOVER_IDS:
            raise DomainError(
                f"Hoechstens {MAX_TURNOVER_IDS} Produkte je Abruf",
                {"angefragt": len(ids)},
            )
    svc = StatsService(db)
    return svc.turnover_rates(ids, days=days)


@router.get("/turnover/{product_id}", response_model=TurnoverResult | None)
def turnover_rate(product_id: int, days: int = Query(90, ge=1, le=365), db: Session = Depends(get_db)):
    svc = StatsService(db)
    result = svc.turnover_rate(product_id, days=days)
    if result is None:
        return None
    return result
