"""Stock routes: booking in/out, availability, expiry."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.domain import DomainError
from app.events import INVENTORY_RESTOCKED, emit
from app.models import StockEntry
from app.schemas import AvailabilityOut, Page, StockEntryCreate, StockEntryOut, StockEntryUpdate
from app.services.stock import StockService

router = APIRouter(prefix="/api/stock", tags=["stock"])

MAX_PAGE_LIMIT = 500


# ----- helpers -----

def _entry_out(e: StockEntry) -> StockEntryOut:
    days = None
    if e.mhd:
        days = (e.mhd - date.today()).days
    return StockEntryOut(
        id=e.id,
        product_id=e.product_id,
        product_name=e.product.name if e.product else "",
        quantity=e.quantity,
        unit=e.unit,
        mhd=e.mhd,
        purchase_date=e.purchase_date,
        location=e.location,
        days_until_expiry=days,
        opened_at=e.opened_at,
    )


# ----- routes -----

@router.get("", response_model=Page[StockEntryOut])
def list_stock(
    product_id: int | None = None,
    location: str | None = None,
    only_positive: bool = True,
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=MAX_PAGE_LIMIT),
    db: Session = Depends(get_db),
):
    svc = StockService(db)
    entries, total = svc.list_entries(
        product_id=product_id,
        location=location,
        only_positive=only_positive,
        offset=offset,
        limit=limit,
    )
    return Page[StockEntryOut](
        items=[_entry_out(e) for e in entries],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/available", response_model=AvailabilityOut)
def get_available(product_id: int, unit: str = "g", db: Session = Depends(get_db)):
    svc = StockService(db)
    total = svc.get_available(product_id, unit)
    return AvailabilityOut(product_id=product_id, unit=unit, total=total)


@router.get("/expiring", response_model=list[StockEntryOut])
def get_expiring(days: int = Query(7, ge=1, le=365), db: Session = Depends(get_db)):
    svc = StockService(db)
    entries = svc.get_expiring(days=days)
    return [_entry_out(e) for e in entries]


@router.get("/{entry_id}", response_model=StockEntryOut)
def get_stock_entry(entry_id: int, db: Session = Depends(get_db)):
    svc = StockService(db)
    entry = svc.get_entry(entry_id)
    if not entry:
        raise DomainError("Bestandseintrag nicht gefunden", {"entry_id": entry_id})
    return _entry_out(entry)


@router.post("", response_model=StockEntryOut, status_code=201)
def add_stock(body: StockEntryCreate, db: Session = Depends(get_db)):
    svc = StockService(db)
    entry = svc.add(body)
    db.commit()
    db.refresh(entry)
    # Event nach Commit: best-effort, blockt Response nicht bei Spine-Ausfall.
    emit(
        event_type=INVENTORY_RESTOCKED,
        external_id=f"stock-entry:{entry.id}",
        summary=f"{entry.quantity} {entry.unit} {entry.product.name if entry.product else f'product:{entry.product_id}'} eingebucht",
        entity_ref=f"product:{entry.product_id}",
        payload={
            "stock_entry_id": entry.id,
            "product_id": entry.product_id,
            "quantity": entry.quantity,
            "unit": entry.unit,
            "mhd": entry.mhd.isoformat() if entry.mhd else None,
            "location": entry.location,
        },
    )
    return _entry_out(entry)


@router.put("/{entry_id}", response_model=StockEntryOut)
def update_stock(entry_id: int, body: StockEntryUpdate, db: Session = Depends(get_db)):
    svc = StockService(db)
    entry = svc.update_entry(entry_id, body)
    db.commit()
    db.refresh(entry)
    return _entry_out(entry)


@router.delete("/{entry_id}", status_code=204)
def delete_stock(entry_id: int, db: Session = Depends(get_db)):
    svc = StockService(db)
    svc.delete_entry(entry_id)
    db.commit()
