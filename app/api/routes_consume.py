"""Consume routes: FIFO consumption, batch recipe consumption."""

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import begin_immediate, get_db
from app.events import INVENTORY_LOW_STOCK, INVENTORY_UPDATED, emit
from app.schemas import ConsumeRecipeRequest, ConsumeRequest, ConsumptionEventOut
from app.services.stock import StockService, check_low_stock

router = APIRouter(prefix="/api/stock", tags=["consume"])


def _emit_consume_events(db: Session, product_ids: set[int]) -> None:
    """Nach Commit: ein inventory.updated pro Produkt + low_stock-Event wenn unterm Minimum."""
    today_iso = date.today().isoformat()
    for pid in product_ids:
        emit(
            event_type=INVENTORY_UPDATED,
            external_id=f"product:{pid}:{today_iso}",
            summary=f"Bestand für product:{pid} aktualisiert",
            entity_ref=f"product:{pid}",
            payload={"product_id": pid},
        )
        low = check_low_stock(db, pid)
        if low:
            emit(
                event_type=INVENTORY_LOW_STOCK,
                external_id=f"low-stock:{pid}:{today_iso}",
                summary=(
                    f"{low['product_name']} unter Mindestbestand: "
                    f"{low['current_stock']} {low['min_stock_unit']} "
                    f"(min: {low['min_stock']})"
                ),
                severity="medium" if low["current_stock"] > 0 else "high",
                entity_ref=f"product:{pid}",
                payload=low,
            )


@router.post("/consume", response_model=list[ConsumptionEventOut])
def consume(body: ConsumeRequest, db: Session = Depends(get_db)):
    svc = StockService(db)
    with begin_immediate(db):
        events = svc.consume(
            product_id=body.product_id,
            amount=body.amount,
            unit=body.unit,
            reason=body.reason,
            source=body.source,
            ref_type=body.ref_type,
            ref_id=body.ref_id,
        )
    _emit_consume_events(db, {body.product_id})
    return [ConsumptionEventOut.model_validate(e) for e in events]


@router.post("/consume-recipe", response_model=list[ConsumptionEventOut])
def consume_recipe(body: ConsumeRecipeRequest, db: Session = Depends(get_db)):
    svc = StockService(db)
    ingredients = [ing.model_dump() for ing in body.ingredients]
    with begin_immediate(db):
        events = svc.consume_for_recipe(
            recipe_ingredients=ingredients,
            source=ingredients[0].get("source", "mealprep") if ingredients else "mealprep",
            ref_type=ingredients[0].get("ref_type") if ingredients else None,
            ref_id=ingredients[0].get("ref_id") if ingredients else None,
        )
    _emit_consume_events(db, {ing["product_id"] for ing in ingredients})
    return [ConsumptionEventOut.model_validate(e) for e in events]
