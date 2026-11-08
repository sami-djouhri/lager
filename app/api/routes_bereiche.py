"""Bereiche: die feste Liste und je Bereich ein Satz fuer die Startseite."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.bereiche import uebersicht
from app.db import get_db
from app.schemas import BereichOut

router = APIRouter(prefix="/api/bereiche", tags=["bereiche"])


@router.get("", response_model=list[BereichOut])
def bereiche(db: Session = Depends(get_db)):
    return uebersicht(db)
